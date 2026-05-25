import random

from game.combat_simulation import SimulationConfig, build_simulation_mob_preset, simulate_single_combat
from game.combat_simulation_archetypes import (
    EXECUTABLE_POLICY_REGISTRY,
    REQUIRED_ARCHETYPE_IDS,
    REQUIRED_PLAYER_FIELDS,
    REQUIRED_POWER_TIERS,
    ALLOWED_OFFHAND_PROFILES,
    build_archetype_player_preset,
    get_archetype_metadata,
    list_alpha_archetype_ids,
    list_simulation_power_tiers,
    validate_archetype_preset_coverage,
)


def test_required_archetype_ids_are_present():
    assert set(list_alpha_archetype_ids()) == set(REQUIRED_ARCHETYPE_IDS)


def test_required_power_tiers_are_present():
    assert set(list_simulation_power_tiers()) == set(REQUIRED_POWER_TIERS)


def test_every_archetype_tier_preset_builds_and_has_required_fields():
    for archetype_id in REQUIRED_ARCHETYPE_IDS:
        for power_tier in REQUIRED_POWER_TIERS:
            preset = build_archetype_player_preset(archetype_id, power_tier)
            for field in REQUIRED_PLAYER_FIELDS:
                assert field in preset, f"{archetype_id}@{power_tier} missing {field}"


def test_archetype_metadata_shape_and_preferred_skill_metadata():
    for archetype_id in REQUIRED_ARCHETYPE_IDS:
        metadata = get_archetype_metadata(archetype_id)
        assert metadata["id"] == archetype_id
        assert metadata["role_tags"]
        assert metadata["strengths"]
        assert metadata["weaknesses"]
        assert metadata["preferred_policy_id"]
        assert isinstance(metadata["preferred_skill_ids"], list)


def test_validate_archetype_preset_coverage_has_no_errors():
    assert validate_archetype_preset_coverage() == []


def test_all_archetypes_can_run_identity_visible_smoke_simulation_without_rewards_context():
    mob = build_simulation_mob_preset("forest_boar")

    for archetype_id in REQUIRED_ARCHETYPE_IDS:
        player = build_archetype_player_preset(archetype_id, "identity_visible")
        policy_factory = EXECUTABLE_POLICY_REGISTRY["always_attack"]["factory"]
        result = simulate_single_combat(
            player,
            mob,
            policy=policy_factory(),
            config=SimulationConfig(seed=11, max_turns=40),
        )

        assert result.turns > 0
        assert result.winner in {"player", "mob", "none"}
        assert isinstance(result.actions_used, dict)
        assert "normal_attack" in result.actions_used
        assert not hasattr(result, "exp")
        assert not hasattr(result, "gold")
        assert not hasattr(result, "loot")


def test_executable_policy_registry_uses_only_safe_existing_policy_actions():
    safe_ids = {"always_attack", "always_guard_fallback", "scripted_smoke"}
    executable_ids = {
        policy_id for policy_id, item in EXECUTABLE_POLICY_REGISTRY.items() if item.get("executable") is True
    }
    assert executable_ids == safe_ids


def test_no_route_class_matrix_report_in_archetype_module():
    # Scope guard: this PR defines presets + metadata only.
    assert "route_class_matrix" not in EXECUTABLE_POLICY_REGISTRY


def test_simulation_seed_restores_global_random_state():
    random.seed(2026)
    before = random.getstate()

    player = build_archetype_player_preset("guardian_shield_1h", "identity_visible")
    mob = build_simulation_mob_preset("forest_boar")
    simulate_single_combat(player, mob, config=SimulationConfig(seed=99, max_turns=20))

    after = random.getstate()
    assert before == after


def test_preset_encumbrance_and_offhand_profiles_are_valid():
    for archetype_id in REQUIRED_ARCHETYPE_IDS:
        for power_tier in REQUIRED_POWER_TIERS:
            preset = build_archetype_player_preset(archetype_id, power_tier)
            encumbrance = preset.get("encumbrance")
            assert encumbrance is None or isinstance(encumbrance, (int, float))
            assert not isinstance(encumbrance, str)
            assert preset.get("offhand_profile") in ALLOWED_OFFHAND_PROFILES


def test_dagger_archetypes_do_not_use_dual_offhand_profile():
    for archetype_id in ("daggers_venom", "daggers_evasion"):
        metadata = get_archetype_metadata(archetype_id)
        assert metadata["offhand_profile"] == "none"
        for power_tier in REQUIRED_POWER_TIERS:
            preset = build_archetype_player_preset(archetype_id, power_tier)
            assert preset["offhand_profile"] != "dual"
            assert preset["offhand_profile"] == "none"


def test_get_archetype_metadata_returns_deep_copy():
    metadata = get_archetype_metadata("guardian_shield_1h")
    metadata["role_tags"].append("mutated")
    metadata["preferred_skill_ids"].append("mutated_skill")

    fresh = get_archetype_metadata("guardian_shield_1h")
    assert "mutated" not in fresh["role_tags"]
    assert "mutated_skill" not in fresh["preferred_skill_ids"]


def test_validate_archetype_preset_coverage_collects_missing_metadata_error_without_abort(monkeypatch):
    from game import combat_simulation_archetypes as csa

    patched = dict(csa.ARCHETYPE_METADATA)
    patched.pop("guardian_shield_1h", None)
    monkeypatch.setattr(csa, "ARCHETYPE_METADATA", patched)

    errors = csa.validate_archetype_preset_coverage()
    assert any(err == "guardian_shield_1h: missing metadata" for err in errors)
