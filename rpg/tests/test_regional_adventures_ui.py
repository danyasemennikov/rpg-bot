import asyncio
import re

from database import get_connection, get_player
from game.pve_live import (
    SPAWN_STATE_ACTIVE, SPAWN_STATE_RESPAWNING,
    ensure_location_pve_spawn_instances,
)
from game.regional_opportunities import nearby, page
from handlers.regional import _list_screen, build_detail, build_regional_home, handle_regional_buttons


def _player(location='hub_westwild', lang='en'):
    conn = get_connection()
    conn.execute(
        'UPDATE players SET location_id=?, lang=?, travel_revision=travel_revision+1 WHERE telegram_id=1',
        (location, lang),
    )
    conn.commit(); conn.close()
    return dict(get_player(1))


def _callbacks(markup):
    return [button.callback_data for row in markup.inline_keyboard for button in row]


def test_home_has_exact_six_peer_views_and_safe_callbacks():
    text, markup = build_regional_home(_player())
    callbacks = _callbacks(markup)
    assert callbacks[:6] == [
        'rv:v:n:0:all', 'rv:v:l:0:all', 'rv:v:p:0:all',
        'rv:v:r:0:all', 'rv:v:s:0:all', 'rv:v:w:0:all',
    ]
    assert 'global completion' in text.lower()
    assert all(len(value.encode('utf-8')) <= 64 for value in callbacks)


def test_pagination_is_six_stable_rows_and_clamped():
    rows = [{'content_id': f'x{index}'} for index in range(14)]
    assert [row['content_id'] for row in page(rows, 0)[0]] == [f'x{i}' for i in range(6)]
    assert [row['content_id'] for row in page(rows, 99)[0]] == ['x12', 'x13']
    assert page(rows, -2)[1:] == (0, 3)


def test_busy_and_respawning_mixed_recipe_remain_visible():
    player = _player('frostspine_n6')
    ensure_location_pve_spawn_instances(location_id='frostspine_n6')
    conn = get_connection()
    conn.execute(
        "UPDATE pve_spawn_instances SET state=? WHERE location_id=? AND mob_id='stone_beetle'",
        (SPAWN_STATE_ACTIVE, 'frostspine_n6'),
    )
    conn.commit(); conn.close()
    row = next(row for row in nearby(player) if row['content_id'] == 'rav1_frostspine_n6_pass')
    assert row['status'] == 'busy'
    text, markup = _list_screen(player, 'n', 0, 'all')
    assert 'busy' in text.lower()
    assert 'rv:d:e:rav1_frostspine_n6_pass' in _callbacks(markup)

    conn = get_connection()
    conn.execute(
        "UPDATE pve_spawn_instances SET state=?, respawn_available_at=datetime('now','+20 seconds') "
        "WHERE location_id=? AND mob_id='stone_beetle'",
        (SPAWN_STATE_RESPAWNING, 'frostspine_n6'),
    )
    conn.commit(); conn.close()
    row = next(row for row in nearby(player) if row['content_id'] == 'rav1_frostspine_n6_pass')
    assert row['status'] == 'respawning'
    assert row['data']['respawn_seconds'] > 0


def test_existing_mixed_and_named_targets_use_real_labels_and_short_actions():
    for location, content_id, expected_prefix in (
        ('westwild_n8', 'westwild_n8_mixed', 'fight_mixed_'),
        ('westwild_n3', 'greyfang', 'fight_special_'),
        ('sunscar_n8a2', 'salt_ridge_drifter', 'fight_special_'),
    ):
        player = _player(location)
        row = next(row for row in nearby(player) if row['content_id'] == content_id)
        assert row['status'] == 'available'
        text, markup = build_detail(player, 'e', content_id)
        assert content_id not in text
        action = next(value for value in _callbacks(markup) if value.startswith(expected_prefix))
        assert len(action.encode('utf-8')) <= 64


def test_all_locale_surfaces_stay_within_message_budgets_and_hide_location_ids():
    internal_id = re.compile(r'(?:westwild|frostspine|ashen|mireveil|sunscar)_[a-z0-9]+')
    for lang in ('en', 'ru', 'es'):
        player = _player('hub_mireveil', lang)
        surfaces = [build_regional_home(player), _list_screen(player, 'w', 0, 'all')]
        surfaces.append(build_detail(player, 'p', 'mv_ferry_crew'))
        for text, markup in surfaces:
            assert len(text) <= 3000
            assert not internal_id.search(text)
            buttons = [button for row in markup.inline_keyboard for button in row]
            assert len(buttons) <= 12
            assert len(markup.inline_keyboard) <= 10
            assert all(len(button.callback_data.encode('utf-8')) <= 64 for button in buttons)


class _User:
    id = 1


class _Query:
    def __init__(self, data):
        self.data = data
        self.from_user = _User()
        self.answers = []
        self.edits = []

    async def answer(self, text=None, **kwargs):
        self.answers.append((text, kwargs))

    async def edit_message_text(self, text, **kwargs):
        self.edits.append((text, kwargs))


class _Update:
    def __init__(self, data):
        self.callback_query = _Query(data)


def test_real_handler_answers_malformed_and_stale_callbacks():
    _player()
    malformed = _Update('rv:not-valid')
    asyncio.run(handle_regional_buttons(malformed, None))
    assert malformed.callback_query.answers and malformed.callback_query.edits
    stale = _Update('rv:a:0000000000000000')
    asyncio.run(handle_regional_buttons(stale, None))
    assert stale.callback_query.answers[0][1].get('show_alert') is True
    assert stale.callback_query.edits
