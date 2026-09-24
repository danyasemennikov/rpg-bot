from handlers.professions import _recipe_name
from game.profession_recipes import ACTIVE_RECIPES
from locales.professions import PROFESSION_KEYS, STRINGS


def test_locale_parity_and_callback_sized_ids():
    for lang in ('ru','en','es'):
        assert set(STRINGS[lang]['names']) == set(PROFESSION_KEYS)
        assert all(_recipe_name(recipe, lang) for recipe in ACTIVE_RECIPES)
    assert all(len(f'pe_r:{recipe.recipe_id}'.encode()) <= 64 for recipe in ACTIVE_RECIPES)
