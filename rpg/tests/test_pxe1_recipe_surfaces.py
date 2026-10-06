import pytest
from database import get_connection,get_player
from game.player_experience_schema import grant_player_pxe1_starters
from game.player_ui import validate_surface
from game.profession_recipes import ACTIVE_RECIPES
from handlers.professions import build_recipe
from handlers.recipe_views import recipe_card


@pytest.mark.parametrize('lang',['ru','en','es'])
def test_all_eighty_three_recipe_cards_compact_tool_output_has_no_sale_value(lang):
    conn = get_connection()
    conn.execute('BEGIN IMMEDIATE')
    grant_player_pxe1_starters(conn,1,now_ms=1000,acquired_via='starter')
    conn.commit()
    conn.close()
    player = dict(get_player(1))
    player['lang'] = lang
    for recipe in ACTIVE_RECIPES:
        text,keyboard = build_recipe(player,recipe.recipe_id)
        validate_surface(text,keyboard)
        assert 'pxe1.' not in text and 'professions.' not in text
        assert len([b for row in keyboard.inline_keyboard for b in row if b.callback_data.startswith('pe_m:')])==0
        if recipe.output_spec.kind=='tool':
            text,keyboard = recipe_card(player,recipe.recipe_id,details=True)
            validate_surface(text,keyboard,long_detail=True)
            from game.i18n import t
            assert t('professions.output_sale',lang,gold=0) not in text
            if recipe.output_spec.profession_key in {'woodcutting','mining'} and recipe.output_spec.tool_tier>1:
                text,keyboard = recipe_card(player,recipe.recipe_id,commission=True)
                validate_surface(text,keyboard)
                assert 'pxe1.' not in text
