"""Frozen RAV1-1 regional content catalogue.

This module is deliberately data-only.  The project runtime is bounded to the
seven definitions below; it is not a general quest language.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


CATALOG_VERSION = 1
OBJECTIVE_KINDS = frozenset({"fact", "deliver", "kill", "encounter", "craft", "respond", "choose"})
REGION_ORDER = ("ww", "fs", "ar", "ss", "mv")


@dataclass(frozen=True)
class Reward:
    xp: int = 0
    gold: int = 0
    items: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True)
class ObjectiveDefinition:
    objective_id: str
    kind: Literal["fact", "deliver", "kill", "encounter", "craft", "respond", "choose"]
    required: int
    locations: tuple[str, ...]
    target: dict


@dataclass(frozen=True)
class StepDefinition:
    step_id: str
    mode: Literal["all", "any"]
    objectives: tuple[ObjectiveDefinition, ...]


@dataclass(frozen=True)
class ProjectDefinition:
    project_id: str
    catalog_version: int
    region_id: str
    text_prefix: str
    start_locations: tuple[str, ...]
    speaker_id: str | None
    public: bool
    steps: tuple[StepDefinition, ...]
    reward: Reward


@dataclass(frozen=True)
class InteractionDefinition:
    content_id: str
    catalog_version: int
    kind: Literal["discovery", "inspect", "request", "cache", "standing"]
    region_id: str
    location_id: str
    speaker_id: str | None
    public: bool
    requires_fact_id: str | None
    text_prefix: str
    cost_items: tuple[tuple[str, int], ...]
    reward: Reward


def _objective(objective_id: str, kind: str, locations: tuple[str, ...], target: dict,
               required: int = 1) -> ObjectiveDefinition:
    return ObjectiveDefinition(objective_id, kind, required, locations, target)


PROJECTS = (
    ProjectDefinition(
        "ww_tool_roll", 1, "route_westwild", "rav1.content.ww_tool_roll",
        ("hub_westwild",), "mara", True,
        (
            StepDefinition("recover", "all", (_objective(
                "wolf", "kill", ("westwild_n3",),
                {"mob_id": "forest_wolf", "profiles": ("normal", "elite"), "special": "any"},
            ),)),
            StepDefinition("return", "all", (_objective(
                "report", "respond", ("hub_westwild",), {"action_id": "report"},
            ),)),
        ), Reward(40, 18),
    ),
    ProjectDefinition(
        "fs_jammed_sled", 1, "route_frostspine", "rav1.content.fs_jammed_sled",
        ("hub_frostspine", "old_mine_entrance"), "iven", True,
        (
            StepDefinition("damage", "all", (_objective(
                "inspect", "fact", ("old_mine_entrance",), {"fact_id": "fs_sled_damage"},
            ),)),
            StepDefinition("repair", "any", (
                _objective("materials", "deliver", ("old_mine_entrance",),
                           {"items": (("wood_common", 2), ("iron_ore", 1))}),
                _objective("clear_lizard", "kill", ("frostspine_n2",),
                           {"mob_id": "rock_lizard", "profiles": ("normal",), "special": "ordinary"}),
            )),
            StepDefinition("report", "all", (_objective(
                "receipt", "respond", ("hub_frostspine",), {"action_id": "receipt"},
            ),)),
        ), Reward(70, 30, (("enhance_shard", 1),)),
    ),
    ProjectDefinition(
        "ar_two_names", 1, "route_ashen_ruins", "rav1.content.ar_two_names",
        ("hub_ashen_ruins",), "sera", True,
        (
            StepDefinition("evidence", "all", (
                _objective("temple", "fact", ("ashen_n3a2",), {"fact_id": "ar_temple_names"}),
                _objective("garden", "fact", ("ashen_n3c1",), {"fact_id": "ar_garden_ledger"}),
            )),
            StepDefinition("record", "all", (_objective(
                "attribution", "choose", ("hub_ashen_ruins",),
                {"choice_id": "attribution", "values": ("shared_credit", "leave_unattributed")},
            ),)),
        ), Reward(50, 20),
    ),
    ProjectDefinition(
        "ar_unquiet_storehouse", 1, "route_ashen_ruins", "rav1.content.ar_unquiet_storehouse",
        ("hub_ashen_ruins", "ashen_n3b1"), "sera", True,
        (
            StepDefinition("seal", "all", (_objective(
                "mark", "fact", ("ashen_n3b1",), {"fact_id": "ar_storehouse_seal"},
            ),)),
            StepDefinition("watch", "all", (_objective(
                "guard", "kill", ("ashen_n3b1",),
                {"mob_id": "skeleton_guard", "profiles": ("normal",), "special": "ordinary"},
            ),)),
            StepDefinition("disposition", "all", (_objective(
                "seal_fate", "choose", ("hub_ashen_ruins",),
                {"choice_id": "seal_fate", "values": ("archive_seal", "leave_seal")},
            ),)),
        ), Reward(80, 30),
    ),
    ProjectDefinition(
        "mv_ferry_crew", 1, "route_mireveil", "rav1.content.mv_ferry_crew",
        ("hub_mireveil", "mireveil_n5"), "oren", True,
        (
            StepDefinition("trail", "all", (
                _objective("ford", "fact", ("mireveil_n5",), {"fact_id": "mv_ford_marks"}),
                _objective("channel", "fact", ("mireveil_n8",), {"fact_id": "mv_channel_rope"}),
            )),
            StepDefinition("clear", "all", (_objective(
                "channel_threat", "encounter", ("mireveil_n6",),
                {"mixed_encounter_id": "rav1_mireveil_n6_crosscurrent"},
            ),)),
            StepDefinition("salvage", "all", (_objective(
                "cargo", "choose", ("mireveil_n8",),
                {"choice_id": "cargo", "values": ("save_supplies", "save_log")},
            ),)),
            StepDefinition("return", "all", (_objective(
                "report", "respond", ("hub_mireveil",), {"action_id": "report"},
            ),)),
        ), Reward(100, 40, (("health_potion_small", 2),)),
    ),
    ProjectDefinition(
        "ss_camp_bearings", 1, "route_sunscar", "rav1.content.ss_camp_bearings",
        ("sunscar_n8a1",), None, False,
        (
            StepDefinition("bearings", "all", (
                _objective("camp", "fact", ("sunscar_n8a1",), {"fact_id": "ss_camp_marks"}),
                _objective("pillars", "fact", ("sunscar_n8a2",), {"fact_id": "ss_pillar_shadow"}),
            )),
            StepDefinition("cache", "all", (_objective(
                "open_cache", "respond", ("sunscar_n8a1",), {"action_id": "open_cache"},
            ),)),
        ), Reward(30, 12, (("field_ration", 1),)),
    ),
    ProjectDefinition(
        "mv_medic_practice", 1, "route_mireveil", "rav1.content.mv_medic_practice",
        ("hub_mireveil",), "lida", True,
        (
            StepDefinition("practice", "all", (_objective(
                "fresh_tonics", "craft", (),
                {"recipe_id": "field_tonic", "output_item_id": "health_potion_small"}, required=2,
            ),)),
            StepDefinition("hand_in", "all", (_objective(
                "tonics", "deliver", ("hub_mireveil",),
                {"items": (("health_potion_small", 2),)},
            ),)),
        ), Reward(30, 15),
    ),
)
PROJECTS_BY_ID = {project.project_id: project for project in PROJECTS}


_DISCOVERY_ROWS = (
    ("ww_greyfang_tracks", "route_westwild", "westwild_n3"),
    ("ww_root_marks", "route_westwild", "westwild_n7"),
    ("fs_survey_stone", "route_frostspine", "frostspine_n4"),
    ("ar_temple_names", "route_ashen_ruins", "ashen_n3a2"),
    ("ar_garden_ledger", "route_ashen_ruins", "ashen_n3c1"),
    ("ar_storehouse_seal", "route_ashen_ruins", "ashen_n3b1"),
    ("mv_ford_marks", "route_mireveil", "mireveil_n5"),
    ("mv_fungal_observation", "route_mireveil", "mireveil_n8a1"),
    ("ss_camp_marks", "route_sunscar", "sunscar_n8a1"),
    ("ss_pillar_shadow", "route_sunscar", "sunscar_n8a2"),
)
DISCOVERIES = tuple(
    InteractionDefinition(key, 1, "discovery", region, location, None, False, None,
                          f"rav1.content.{key}", (), Reward())
    for key, region, location in _DISCOVERY_ROWS
)
AUXILIARY_INSPECTIONS = (
    InteractionDefinition("fs_sled_damage", 1, "inspect", "route_frostspine",
                          "old_mine_entrance", None, False, None,
                          "rav1.content.fs_sled_damage", (), Reward()),
    InteractionDefinition("mv_channel_rope", 1, "inspect", "route_mireveil",
                          "mireveil_n8", None, False, None,
                          "rav1.content.mv_channel_rope", (), Reward()),
)
DIRECT_REQUESTS = (
    InteractionDefinition("ww_woodcutter_provisions", 1, "request", "route_westwild",
                          "hub_westwild", "mara", True, None,
                          "rav1.content.ww_woodcutter_provisions", (("field_ration", 2),), Reward(20, 18)),
    InteractionDefinition("mv_medic_table", 1, "request", "route_mireveil",
                          "hub_mireveil", "lida", True, None,
                          "rav1.content.mv_medic_table", (("herb_common", 4),), Reward(20, 18)),
)
CACHES = (
    InteractionDefinition("ww_root_cache", 1, "cache", "route_westwild", "westwild_n7",
                          None, False, "ww_root_marks", "rav1.content.ww_root_cache", (),
                          Reward(0, 0, (("health_potion_small", 1), ("enhance_shard", 1)))),
)
STANDING_DELIVERIES = (
    InteractionDefinition("ww_ration_order", 1, "standing", "route_westwild", "hub_westwild",
                          "mara", True, None, "rav1.content.ww_ration_order",
                          (("field_ration", 2),), Reward(0, 10)),
    InteractionDefinition("fs_forge_supplies", 1, "standing", "route_frostspine", "hub_frostspine",
                          None, True, None, "rav1.content.fs_forge_supplies",
                          (("iron_ore", 2), ("coal", 2)), Reward(0, 20)),
    InteractionDefinition("mv_stew_order", 1, "standing", "route_mireveil", "hub_mireveil",
                          "oren", True, None, "rav1.content.mv_stew_order",
                          (("pe_marsh_stew", 2),), Reward(0, 12)),
)
INTERACTIONS = DISCOVERIES + AUXILIARY_INSPECTIONS + DIRECT_REQUESTS + CACHES + STANDING_DELIVERIES
INTERACTIONS_BY_ID = {entry.content_id: entry for entry in INTERACTIONS}
FACTS_BY_ID = {entry.content_id: entry for entry in DISCOVERIES + AUXILIARY_INSPECTIONS}


REGIONAL_SUMMARIES = (
    {"content_id": "region_westwild", "region_code": "ww", "region_id": "route_westwild", "hub": "hub_westwild"},
    {"content_id": "region_frostspine", "region_code": "fs", "region_id": "route_frostspine", "hub": "hub_frostspine"},
    {"content_id": "region_ashen_ruins", "region_code": "ar", "region_id": "route_ashen_ruins", "hub": "hub_ashen_ruins"},
    {"content_id": "region_sunscar", "region_code": "ss", "region_id": "route_sunscar", "hub": "hub_sunscar"},
    {"content_id": "region_mireveil", "region_code": "mv", "region_id": "route_mireveil", "hub": "hub_mireveil"},
)
REGIONAL_SUMMARIES_BY_CODE = {row["region_code"]: row for row in REGIONAL_SUMMARIES}

SPECIAL_TARGETS = (
    {"content_id": "greyfang", "location_id": "westwild_n3", "mob_id": "forest_wolf",
     "key": "greyfang", "spawn_profile": "normal", "count": 1},
    {"content_id": "salt_ridge_drifter", "location_id": "sunscar_n8a2", "mob_id": "air_elemental",
     "key": "salt_ridge_drifter", "spawn_profile": "elite", "count": 1},
)
MIXED_ENCOUNTERS = (
    {"content_id": "rav1_frostspine_n6_pass", "location_id": "frostspine_n6",
     "units": (("mountain_stone_golem", "front"), ("stone_beetle", "melee"))},
    {"content_id": "rav1_mireveil_n6_crosscurrent", "location_id": "mireveil_n6",
     "units": (("giant_leech", "melee"), ("water_snake", "melee"))},
)


def all_top_level_ids() -> tuple[str, ...]:
    return tuple(
        [p.project_id for p in PROJECTS]
        + [i.content_id for i in INTERACTIONS]
        + [r["content_id"] for r in REGIONAL_SUMMARIES]
        + [r["content_id"] for r in SPECIAL_TARGETS]
        + [r["content_id"] for r in MIXED_ENCOUNTERS]
    )


def validate_catalogue() -> None:
    """Fail startup when the frozen catalogue or one of its references drifts."""
    from game.crafting_runtime import LIVE_RECIPE_IDS, get_recipe
    from game.items_data import get_item
    from game.locations import get_location
    from game.mobs import get_mob

    errors: list[str] = []
    if len(PROJECTS) != 7 or sum(len(p.steps) for p in PROJECTS) != 18:
        errors.append("project/step count")
    objectives = [o for p in PROJECTS for s in p.steps for o in s.objectives]
    if len(objectives) != 22 or {o.kind for o in objectives} != OBJECTIVE_KINDS:
        errors.append("objective count/kinds")
    if len(all_top_level_ids()) != 34 or len(set(all_top_level_ids())) != 34:
        errors.append("top-level record count/identity")
    if len(DISCOVERIES) != 10 or len(AUXILIARY_INSPECTIONS) != 2:
        errors.append("fact counts")
    if len(DIRECT_REQUESTS) != 2 or len(CACHES) != 1 or len(STANDING_DELIVERIES) != 3:
        errors.append("interaction counts")
    if len(REGIONAL_SUMMARIES) != 5 or len(SPECIAL_TARGETS) != 2 or len(MIXED_ENCOUNTERS) != 2:
        errors.append("regional/world counts")

    for project in PROJECTS:
        if project.catalog_version != 1 or not 1 <= len(project.steps) <= 4:
            errors.append(f"{project.project_id}: version/steps")
        if sum(step.mode == "any" for step in project.steps) > 1:
            errors.append(f"{project.project_id}: too many ANY steps")
        choice_count = 0
        objective_ids: set[str] = set()
        for location in project.start_locations:
            if not get_location(location):
                errors.append(f"{project.project_id}: unknown start {location}")
        for step in project.steps:
            if not 1 <= len(step.objectives) <= 2 or step.mode not in {"all", "any"}:
                errors.append(f"{project.project_id}.{step.step_id}: shape")
            for objective in step.objectives:
                if objective.objective_id in objective_ids:
                    errors.append(f"{project.project_id}: duplicate objective {objective.objective_id}")
                objective_ids.add(objective.objective_id)
                if objective.kind not in OBJECTIVE_KINDS or objective.required < 1:
                    errors.append(f"{project.project_id}.{objective.objective_id}: kind/required")
                if objective.kind != "craft" and not objective.locations:
                    errors.append(f"{project.project_id}.{objective.objective_id}: missing location")
                if any(not get_location(location) for location in objective.locations):
                    errors.append(f"{project.project_id}.{objective.objective_id}: unknown location")
                if objective.kind == "fact" and objective.target.get("fact_id") not in FACTS_BY_ID:
                    errors.append(f"{project.project_id}.{objective.objective_id}: unknown fact")
                if objective.kind == "kill" and not get_mob(objective.target.get("mob_id")):
                    errors.append(f"{project.project_id}.{objective.objective_id}: unknown mob")
                if objective.kind == "craft":
                    recipe_id = objective.target.get("recipe_id")
                    recipe = get_recipe(recipe_id)
                    if recipe_id not in LIVE_RECIPE_IDS or not recipe or recipe.output_item_id != objective.target.get("output_item_id"):
                        errors.append(f"{project.project_id}.{objective.objective_id}: unknown recipe/output")
                if objective.kind in {"deliver", "craft"}:
                    item_ids = ([item for item, _ in objective.target.get("items", ())]
                                if objective.kind == "deliver" else [objective.target.get("output_item_id")])
                    if any(not get_item(item_id) for item_id in item_ids):
                        errors.append(f"{project.project_id}.{objective.objective_id}: unknown item")
                if objective.kind == "choose":
                    choice_count += 1
                    if len(tuple(objective.target.get("values", ()))) != 2:
                        errors.append(f"{project.project_id}.{objective.objective_id}: choice values")
        if choice_count > 1:
            errors.append(f"{project.project_id}: too many choices")
        for item_id, quantity in project.reward.items:
            if quantity <= 0 or not get_item(item_id):
                errors.append(f"{project.project_id}: invalid reward item")

    for interaction in INTERACTIONS:
        if not get_location(interaction.location_id):
            errors.append(f"{interaction.content_id}: unknown location")
        if interaction.requires_fact_id and interaction.requires_fact_id not in FACTS_BY_ID:
            errors.append(f"{interaction.content_id}: unknown prerequisite fact")
        for item_id, quantity in interaction.cost_items + interaction.reward.items:
            if quantity <= 0 or not get_item(item_id):
                errors.append(f"{interaction.content_id}: invalid item")
    if errors:
        raise RuntimeError("invalid RAV1 catalogue: " + "; ".join(errors))

