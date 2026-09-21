from __future__ import annotations

import inspect
import json
from pathlib import Path

from game.build_contract import FAMILIES, RULES_VERSION
from game.combat_identity_simulation import (
    ROLE_SCENARIOS,
    build_enemy_roster,
    build_legal_lab_actor,
    build_mixed_enemy_roster,
    choose_visible_action,
    paired_difference,
    simulate_v1_encounter,
    snapshot_matrix,
    validate_lab_actor,
)
import game.combat_identity_simulation as simulation


def test_simulator_uses_shared_v1_authorities_and_no_legacy_simulator_import():
    source = inspect.getsource(simulation)
    assert 'from game.combat_identity import (' in source
    assert 'evaluate_action' in source
    assert 'evaluate_enemy_action' in source
    assert 'advance_affected_side' in source
    assert 'from game.combat_simulation import' not in source
    assert 'from game.pack_simulation import' not in source


def test_legal_snapshot_matrix_covers_all_branches_stages_mixes_and_extremes():
    matrix = snapshot_matrix()
    assert matrix['independent_progression_axes'] is True
    assert matrix['stages'] == [
        {'level': 1, 'mastery_level': 1},
        {'level': 3, 'mastery_level': 3},
        {'level': 6, 'mastery_level': 8},
        {'level': 10, 'mastery_level': 14},
        {'level': 15, 'mastery_level': 20},
    ]
    assert matrix['snapshot_count'] == 100
    assert all(not row['validation_errors'] for row in matrix['snapshots'])
    assert {row['family'] for row in matrix['cross_branch_m20_15_plus_6']} == {
        'sword_1h', 'daggers', 'magic_staff', 'holy_staff',
    }
    assert all(row['points_spent'] == 21 for row in matrix['cross_branch_m20_15_plus_6'])
    assert all(len(row['capstones']) == 1 for row in matrix['cross_branch_m20_15_plus_6'])
    assert matrix['progression_comparison_count'] == 100
    assert {
        row['gear_set'] for row in matrix['progression_comparisons']
    } == {'entry_weapon_only', 'common_t1_full'}
    assert all(
        set(row['branches']) == {'A', 'B'}
        and not row['branches']['A']['validation_errors']
        and not row['branches']['B']['validation_errors']
        for row in matrix['progression_comparisons']
    )
    assert len(matrix['stat_swap_variants']) == 10
    assert len(matrix['extreme_formula_probes_not_balance_claims']) == 40


def test_all_twenty_m3_entry_builds_are_legal_and_complete_a_real_single_smoke():
    winners = []
    for family in FAMILIES:
        for branch in ('A', 'B'):
            actor = build_legal_lab_actor(
                family, branch, level=3, mastery_level=3,
                gear_set='entry_weapon_only',
            )
            assert validate_lab_actor(actor) == []
            assert actor['provenance']['gear_gold_cost'] == 45
            result = simulate_v1_encounter(
                actor, build_enemy_roster(('westwild_rabbit',)), seed=7,
            )
            winners.append(result['winner'])
            assert result['rules_version'] == RULES_VERSION
            assert result['consumables'] == 0
            assert result['fallbacks'] == 0
    assert winners == ['players'] * 20


def test_mixed_roster_keeps_exact_real_unit_ids_and_formations():
    enemies = build_mixed_enemy_roster('westwild_n8_mixed')
    assert [enemy['unit_id'] for enemy in enemies] == ['unit-1', 'unit-2', 'unit-3']
    assert [(enemy['mob_id'], enemy['formation']) for enemy in enemies] == [
        ('bear', 'front'), ('goblin_hunter', 'melee'), ('goblin_shaman', 'support'),
    ]


def test_normal_branch_aware_and_best_of_legal_policies_emit_legal_actions():
    actor = build_legal_lab_actor('magic_staff', 'A', level=6, mastery_level=8)
    enemies = build_enemy_roster(('mountain_stone_golem',))
    for policy in ('normal_only', 'branch_aware', 'best_of_legal'):
        action = choose_visible_action(actor, [actor], enemies, policy=policy)
        assert action['kind'] in {'normal', 'skill'}
        result = simulate_v1_encounter(
            actor, enemies, seed=3, policy=policy, max_opportunities=2,
        )
        assert result['event_count'] > 0


def test_stalls_are_explicit_failures_and_paired_interval_is_directional():
    actor = build_legal_lab_actor('holy_staff', 'A', level=6, mastery_level=8)
    result = simulate_v1_encounter(
        actor, build_enemy_roster(('mountain_stone_golem',)),
        seed=4, max_opportunities=1,
    )
    assert result['stalled'] is True
    assert result['winner'] == 'enemies'
    comparison = paired_difference([12, 13, 14, 15], [10, 10, 10, 10])
    assert comparison['advantage_percent'] == 35.0
    assert comparison['ci_excludes_zero'] is True


def test_role_plan_declares_two_axes_for_every_sibling_pair():
    assert len(ROLE_SCENARIOS) == 17
    assert sum(len(scenario['gates']) for scenario in ROLE_SCENARIOS) == 20
    assert {scenario['family'] for scenario in ROLE_SCENARIOS} == set(FAMILIES)


def test_checked_evidence_has_exact_seed_budget_and_passes_frozen_gates():
    path = Path(__file__).parents[1] / 'docs' / 'evidence' / 'character_builds_combat_identity_v1.json'
    evidence = json.loads(path.read_text(encoding='utf-8'))
    assert evidence['rules_version'] == RULES_VERSION
    assert evidence['rng']['paired_seeds'] == list(range(200))
    assert evidence['accessibility']['all_branches_pass'] is True
    assert evidence['roles']['all_gates_pass'] is True
    assert evidence['roles']['gate_count'] == 20
    assert evidence['encounter_matrix']['result_count'] == 240
    assert evidence['snapshot_matrix']['progression_comparison_count'] == 100
    assert len(evidence['snapshot_matrix']['cross_branch_m20_15_plus_6']) == 4
    assert all(
        len(row['capstones']) == 1
        for row in evidence['snapshot_matrix']['cross_branch_m20_15_plus_6']
    )
    assert evidence['authority']['legacy_simulator_used'] is False
    assert all(abs(row['relative_percent']) <= 15 for row in evidence['bounded_numerical_tuning'])
