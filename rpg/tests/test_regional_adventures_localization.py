from game.i18n import t, validate_rav1_locales
from game.regional_catalog import INTERACTIONS, PROJECTS, REGIONAL_SUMMARIES
from handlers.regional import build_regional_home


def test_exact_key_and_placeholder_parity_without_known_fallback():
    validate_rav1_locales()
    for lang in ('ru','en','es'):
        for project in PROJECTS:
            assert not t(f'rav1.content.{project.project_id}.title', lang).startswith('[')
            for step in project.steps:
                assert not t(f'rav1.content.{project.project_id}.step.{step.step_id}', lang).startswith('[')
                for objective in step.objectives:
                    assert not t(f'rav1.content.{project.project_id}.objective.{objective.objective_id}', lang).startswith('[')
        for entry in INTERACTIONS:
            assert not t(f'rav1.content.{entry.content_id}.title', lang).startswith('[')
        for region in REGIONAL_SUMMARIES:
            assert not t(f"rav1.regions.{region['content_id']}.title", lang).startswith('[')


def test_home_has_exact_six_top_level_views_and_callback_budget():
    for lang in ('ru','en','es'):
        text, keyboard = build_regional_home({'telegram_id':1,'lang':lang,'location_id':'capital_city'})
        callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
        top = [value for value in callbacks if value.startswith('rv:v:')][:6]
        assert top == ['rv:v:n:0:all','rv:v:l:0:all','rv:v:p:0:all','rv:v:r:0:all','rv:v:s:0:all','rv:v:w:0:all']
        assert all(len(value.encode('utf-8')) <= 64 for value in callbacks)
        assert len(text) <= 3000
