from collections import Counter

from game.regional_catalog import (
    AUXILIARY_INSPECTIONS, CACHES, DIRECT_REQUESTS, DISCOVERIES, INTERACTIONS,
    MIXED_ENCOUNTERS, OBJECTIVE_KINDS, PROJECTS, REGIONAL_SUMMARIES,
    SPECIAL_TARGETS, STANDING_DELIVERIES, all_top_level_ids, validate_catalogue,
)


def test_frozen_catalogue_counts_and_bounded_shape():
    validate_catalogue()
    assert len(PROJECTS) == 7
    assert sum(len(project.steps) for project in PROJECTS) == 18
    objectives = [objective for project in PROJECTS for step in project.steps for objective in step.objectives]
    assert len(objectives) == 22
    assert {objective.kind for objective in objectives} == OBJECTIVE_KINDS
    assert Counter(objective.kind for objective in objectives) == {
        'fact': 8, 'deliver': 2, 'kill': 3, 'encounter': 1, 'craft': 1, 'respond': 4, 'choose': 3,
    }
    assert sum(step.mode == 'any' for project in PROJECTS for step in project.steps) == 1
    assert sum(objective.kind == 'choose' for objective in objectives) == 3
    assert all(len(project.steps) <= 4 for project in PROJECTS)
    assert all(len(step.objectives) <= 2 for project in PROJECTS for step in project.steps)


def test_frozen_top_level_record_counts():
    assert len(DISCOVERIES) == 10
    assert len(AUXILIARY_INSPECTIONS) == 2
    assert len(DIRECT_REQUESTS) == 2
    assert len(CACHES) == 1
    assert len(STANDING_DELIVERIES) == 3
    assert len(REGIONAL_SUMMARIES) == 5
    assert len(SPECIAL_TARGETS) == 2
    assert len(MIXED_ENCOUNTERS) == 2
    assert len(INTERACTIONS) == 18
    assert len(all_top_level_ids()) == len(set(all_top_level_ids())) == 34


def test_exact_finite_reward_ledger():
    rewards = {project.project_id: project.reward for project in PROJECTS}
    rewards.update({entry.content_id: entry.reward for entry in DIRECT_REQUESTS + CACHES})
    assert len(rewards) == 10
    assert sum(reward.xp for reward in rewards.values()) == 440
    assert sum(reward.gold for reward in rewards.values()) == 201
    items = Counter()
    for reward in rewards.values():
        items.update(dict(reward.items))
    assert items == {'enhance_shard': 2, 'health_potion_small': 3, 'field_ration': 1}


def test_exact_standing_terms_and_zero_xp():
    assert [(entry.content_id, entry.cost_items, entry.reward.gold) for entry in STANDING_DELIVERIES] == [
        ('ww_ration_order', (('field_ration', 2),), 10),
        ('fs_forge_supplies', (('iron_ore', 2), ('coal', 2)), 20),
        ('mv_stew_order', (('pe_marsh_stew', 2),), 12),
    ]
    assert all(entry.reward.xp == 0 and not entry.reward.items for entry in STANDING_DELIVERIES)
