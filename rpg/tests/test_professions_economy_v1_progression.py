from game.gathering_progression import gathering_profession_xp_for_success
from game.profession_progression import apply_profession_xp, crafting_xp_for_success


def test_frozen_gathering_xp_boundaries():
    assert gathering_profession_xp_for_success(current_profession_level=5, required_profession_level=1) == 10
    assert gathering_profession_xp_for_success(current_profession_level=6, required_profession_level=1) == 5
    assert gathering_profession_xp_for_success(current_profession_level=7, required_profession_level=1) == 0
    assert gathering_profession_xp_for_success(current_profession_level=20, required_profession_level=18) == 0


def test_crafting_ceiling_path_and_zero_xp_preservation():
    state = (1, 0)
    for level, crafts in ((1, 3), (6, 2), (12, 2), (18, 1)):
        for _ in range(crafts):
            xp = crafting_xp_for_success(current_level=state[0], current_exp=state[1], recipe_level=level)
            result = apply_profession_xp(*state, xp)
            state = (result.new_level, result.new_exp)
    assert state == (20, 0)
    preserved = apply_profession_xp(20, 123, 0)
    assert (preserved.new_level, preserved.new_exp) == (20, 123)
