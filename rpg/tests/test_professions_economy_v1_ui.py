import asyncio
import json
import re
from types import SimpleNamespace
from unittest.mock import AsyncMock

import database
import pytest
from game.economy_actions import list_receipts, store_receipt
from game.i18n import get_item_description, get_item_name, t
from game.profession_resources import MANDATORY_RESOURCE_IDS
from game.seed import seed_items
from handlers.professions import (
    _recipe_name, build_material, build_mutation_result, build_overview,
    build_profession, build_recipe, build_receipts, build_resource_list,
    handle_profession_buttons,
)
from handlers.location import handle_lower_menu_gather_text
from game.profession_recipes import ACTIVE_RECIPES
from locales.professions import PROFESSION_KEYS, STRINGS


def test_locale_parity_and_callback_sized_ids():
    assert set(STRINGS['ru']) == set(STRINGS['en']) == set(STRINGS['es'])
    for lang in ('ru','en','es'):
        assert set(STRINGS[lang]['names']) == set(PROFESSION_KEYS)
        assert all(_recipe_name(recipe, lang) for recipe in ACTIVE_RECIPES)
    assert all(len(f'pe_r:{recipe.recipe_id}'.encode()) <= 64 for recipe in ACTIVE_RECIPES)


@pytest.mark.parametrize('lang',['ru','en','es'])
def test_timed_tool_and_unknown_history_keeps_dates_and_hides_unrecognized_ids(lang):
    from handlers.professions import _receipt_lines,_receipt_list_label
    from game.player_ui import validate_surface
    base={'created_at':'2026-10-07 12:34:56','consumed':[],'granted':[],
          'gold_delta':0,'gold_after':12,'progression':[],'details':{}}
    cases=[('gather_tick_pxe1','running','pxe1.gather.collecting'),
           ('tool_commission_pxe1','crafted','pxe1.tool.commission'),
           ('tool_repair_pxe1','repaired','pxe1.tool.repair'),
           ('tool_replace_pxe1','replaced','pxe1.tool.replace'),
           ('removed_future_action','removed_future_status','pxe1.common.unknown_historical')]
    for index,(kind,status,key) in enumerate(cases):
        receipt={**base,'action_kind':kind,'status':status,'request_id':f'history:{index}'}
        lines=_receipt_lines(receipt,lang)
        assert t(key,lang) in lines[2]
        assert lines[1]=='2026-10-07 12:34'
        label=_receipt_list_label(receipt,lang)
        assert not any(raw in '\n'.join(lines)+label for raw in ('removed_future_action','removed_future_status','[pxe1.','[professions.'))
        store_conn=database.get_connection()
        store_receipt(store_conn,1,receipt['request_id'],kind,str(index),receipt,catalog_version=2)
        store_conn.commit();store_conn.close()
    player=dict(database.get_player(1));player['lang']=lang
    text,kb=build_receipts(player)
    validate_surface(text,kb,list_view=True)
    assert len([b for row in kb.inline_keyboard for b in row if b.callback_data.startswith('pe_x:')])==5
    assert 'removed_future' not in repr(kb)


def test_known_pev1_content_has_real_parallel_localization():
    item_ids = set(MANDATORY_RESOURCE_IDS) | {recipe.output_spec.item_id for recipe in ACTIVE_RECIPES if recipe.output_spec.item_id}
    for lang in ('ru', 'en', 'es'):
        for item_id in item_ids:
            name = get_item_name(item_id, lang)
            description = get_item_description(item_id, lang)
            assert name and name != item_id and not name.startswith('['), (lang, item_id, name)
            assert description and not description.startswith('['), (lang, item_id, description)
            assert description != t('professions.unknown_item_description', lang, id=item_id)
            if lang != 'ru':
                assert not re.search('[А-Яа-яЁё]', name + description), (lang, item_id)


def test_profession_and_recipe_details_show_contract_fields_and_clickable_ingredients(tmp_path, monkeypatch):
    monkeypatch.setattr(database, 'DB_PATH', str(tmp_path / 'ui.db'))
    database.init_db(); seed_items()
    database.create_player(71, 'ui', 'UI',
        dict.fromkeys(('strength','agility','intuition','vitality','wisdom','luck'), 2), lang='en')
    player = dict(database.get_player(71))
    _, first_keyboard = build_overview(player, 0, group='crafting')
    _, second_keyboard = build_overview(player, 1, group='crafting')
    assert sum(button.callback_data.startswith('pe_p:') for row in first_keyboard.inline_keyboard for button in row) == 6
    assert sum(button.callback_data.startswith('pe_p:') for row in second_keyboard.inline_keyboard for button in row) == 1
    profession, _ = build_profession(player, 'alchemy')
    assert 'Current milestone' in profession and 'Next unlock' in profession and 'training ceiling' in profession
    from handlers.recipe_views import recipe_card
    recipe, keyboard = recipe_card(player, 'pe_sword_1h_01', details=True)
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert 'State: Known' in recipe and 'Output: ×1' in recipe and 'T1, common rarity' in recipe
    assert 'No secondary properties' in recipe and 'trains through level 6' in recipe
    assert 'pe_inputs:pe_sword_1h_01:0' in callbacks
    inputs,inputs_keyboard=recipe_card(player,'pe_sword_1h_01',inputs_page=0)
    assert sum(button.callback_data.startswith('pe_m:') for row in inputs_keyboard.inline_keyboard for button in row)==3
    assert 'Iron' in inputs
    assert 'pe_r:pe_sword_1h_01' in callbacks
    conn = database.get_connection()
    conn.execute("UPDATE player_crafting_professions SET level=5,exp=249 WHERE player_id=71 AND profession_key='alchemy'")
    conn.commit(); conn.close()
    clipped_preview, _ = build_recipe(dict(database.get_player(71)), 'field_tonic')
    assert 'This craft awards 1 profession XP.' in clipped_preview
    conn = database.get_connection()
    conn.execute("UPDATE player_crafting_professions SET level=6,exp=0 WHERE player_id=71 AND profession_key='alchemy'")
    conn.commit(); conn.close()
    zero_preview, _ = build_recipe(dict(database.get_player(71)), 'field_tonic')
    assert 'At your current level this recipe grants 0 XP.' in zero_preview


def test_receipt_pages_use_six_row_offsets_and_one_row_lookahead(tmp_path, monkeypatch):
    monkeypatch.setattr(database, 'DB_PATH', str(tmp_path / 'game.db'))
    database.init_db(); seed_items()
    database.create_player(70, 'receipts', 'Receipts',
        dict.fromkeys(('strength','agility','intuition','vitality','wisdom','luck'), 2), lang='en')
    conn = database.get_connection()
    for index in range(12):
        result = {'schema_version': 1, 'action_kind': 'gather', 'status': 'empty',
                  'player_id': 70, 'location_id': 'capital_city', 'recipe_id': None,
                  'consumed': [], 'granted': [], 'gold_delta': 0, 'gold_after': 100,
                  'progression': [], 'source': {}, 'details': {}}
        store_receipt(conn, 70, f'r{index:02}', 'gather', f'h{index:02}', result)
    conn.commit(); conn.close()

    page0 = list_receipts(70, page=0, page_size=6)
    page1 = list_receipts(70, page=1, page_size=6)
    page2 = list_receipts(70, page=2, page_size=6)
    assert [row['request_id'] for row in page0] == ['r11','r10','r09','r08','r07','r06','r05']
    assert [row['request_id'] for row in page1] == ['r05','r04','r03','r02','r01','r00']
    assert [row['request_id'] for row in page2] == []
    player = dict(database.get_player(70))
    _, keyboard = build_receipts(player, 1)
    receipt_buttons = [button for row in keyboard.inline_keyboard for button in row
                       if button.callback_data.startswith('pe_x:')]
    assert len(receipt_buttons) == 6
    conn = database.get_connection()
    payloads = [conn.execute('SELECT payload FROM player_ui_actions WHERE token=?',
                (button.callback_data.split(':', 1)[1],)).fetchone()['payload'] for button in receipt_buttons]
    conn.close()
    assert payloads == ['r05','r04','r03','r02','r01','r00']
    _, oversized_keyboard = build_receipts(player, 999)
    oversized_receipts = [button for row in oversized_keyboard.inline_keyboard for button in row
                          if button.callback_data.startswith('pe_x:')]
    oversized_nav = [button.callback_data for row in oversized_keyboard.inline_keyboard for button in row
                     if button.callback_data.startswith('pe_h:')]
    conn = database.get_connection()
    oversized_payloads = [conn.execute('SELECT payload FROM player_ui_actions WHERE token=?',
        (button.callback_data.split(':', 1)[1],)).fetchone()['payload'] for button in oversized_receipts]
    conn.close()
    assert oversized_payloads == ['r05','r04','r03','r02','r01','r00']
    assert oversized_nav == ['pe_h:0']
    query = SimpleNamespace(
        from_user=SimpleNamespace(id=70), data='pe_h:999',
        answer=AsyncMock(), edit_message_text=AsyncMock(),
    )
    asyncio.run(handle_profession_buttons(SimpleNamespace(callback_query=query), SimpleNamespace()))
    callback_keyboard = query.edit_message_text.await_args.kwargs['reply_markup']
    callback_nav = [button.callback_data for row in callback_keyboard.inline_keyboard for button in row
                    if button.callback_data.startswith('pe_h:')]
    callback_receipts = [button for row in callback_keyboard.inline_keyboard for button in row
                         if button.callback_data.startswith('pe_x:')]
    assert len(callback_receipts) == 6 and callback_nav == ['pe_h:0']


def test_ru_en_es_profession_callbacks_render_complete_localized_flow(tmp_path, monkeypatch):
    monkeypatch.setattr(database, 'DB_PATH', str(tmp_path / 'callbacks.db'))
    database.init_db(); seed_items()
    rendered_by_language = {}
    for offset, lang in enumerate(('ru', 'en', 'es')):
        player_id = 80 + offset
        database.create_player(player_id, f'callback-{lang}', f'Callback {lang}',
            dict.fromkeys(('strength','agility','intuition','vitality','wisdom','luck'), 2), lang=lang)
        rendered = []
        for callback in (
            'pe_o:0', 'pe_p:herbalism', 'pe_g:herbalism:0',
            'pe_m:herb_common:0', 'pe_p:blacksmith', 'pe_r:pe_sword_1h_01',
        ):
            query = SimpleNamespace(
                from_user=SimpleNamespace(id=player_id), data=callback,
                answer=AsyncMock(), edit_message_text=AsyncMock(),
            )
            asyncio.run(handle_profession_buttons(SimpleNamespace(callback_query=query), SimpleNamespace()))
            query.answer.assert_awaited_once()
            query.edit_message_text.assert_awaited_once()
            rendered.append(query.edit_message_text.await_args.args[0])
        rendered_by_language[lang] = '\n'.join(rendered)
    for lang, rendered in rendered_by_language.items():
        assert rendered.strip() and '[professions.' not in rendered
        if lang != 'ru':
            assert not re.search('[А-Яа-яЁё]', rendered)


def test_historical_gather_recovery_uses_profession_localization(tmp_path, monkeypatch):
    monkeypatch.setattr(database, 'DB_PATH', str(tmp_path / 'historical-gather.db'))
    database.init_db(); seed_items()
    database.create_player(90, 'historical', 'Historical',
        dict.fromkeys(('strength','agility','intuition','vitality','wisdom','luck'), 2), lang='en')
    conn = database.get_connection()
    conn.execute("UPDATE players SET location_id='old_mine_entrance' WHERE telegram_id=90")
    conn.execute("INSERT INTO player_action_receipts(player_id,request_id) VALUES (90,'gather:90:7')")
    conn.commit(); conn.close()
    message = SimpleNamespace(
        text=t('keyboard.gather_mining', 'en'), message_id=7, chat_id=90,
        reply_text=AsyncMock(),
    )
    update = SimpleNamespace(message=message, effective_user=SimpleNamespace(id=90))
    assert asyncio.run(handle_lower_menu_gather_text(update, SimpleNamespace())) is True
    message.reply_text.assert_awaited_once_with(
        t('professions.historical_receipt_unavailable', 'en')
    )


def test_ru_en_es_complete_navigation_and_failure_results_hide_internal_keys(tmp_path, monkeypatch):
    """Fixture-only localization boundary; production acquisition is proved by the journey test."""
    monkeypatch.setattr(database, 'DB_PATH', str(tmp_path / 'localized-ui.db'))
    database.init_db(); seed_items()
    database.create_player(72, 'localized', 'Localized',
        dict.fromkeys(('strength','agility','intuition','vitality','wisdom','luck'), 2), lang='en')
    base = {
        'schema_version': 1, 'player_id': 72, 'location_id': 'capital_city',
        'recipe_id': None, 'consumed': [], 'granted': [], 'gold_delta': 0,
        'gold_after': 100, 'progression': [], 'source': {}, 'details': {},
    }
    learned = {**base, 'action_kind': 'learn', 'status': 'learned',
               'recipe_id': 'pe_sword_1h_01'}
    crafted = {
        **base, 'action_kind': 'craft', 'status': 'crafted', 'recipe_id': 'pe_sword_1h_01',
        'consumed': [{'item_id': 'iron_ore', 'quantity': 3}],
        'granted': [{'item_id': 'field_sword_1h', 'quantity': 1, 'instance_ids': [42],
                     'gear_specs': [{'item_tier': 1, 'rarity': 'common', 'secondary_rolls': []}]}],
        'progression': [{'profession_key': 'blacksmith', 'old_level': 1, 'old_exp': 0,
                         'new_level': 1, 'new_exp': 20, 'xp_awarded': 20}],
    }
    recovery = {**base, 'action_kind': 'consume', 'status': 'used',
                'consumed': [{'item_id': 'pe_oasis_meal', 'quantity': 1}],
                'details': {'heal': 100, 'mana': 50}}
    failures = (
        {**base, 'action_kind': 'craft', 'status': 'missing_materials',
         'details': {'missing': [{'item_id': 'iron_ore', 'required': 3, 'available': 1}]}},
        {**base, 'action_kind': 'gather', 'status': 'profession_locked'},
        {**base, 'action_kind': 'craft', 'status': 'stale_action'},
    )

    for lang in ('ru', 'en', 'es'):
        player = dict(database.get_player(72)); player['lang'] = lang
        stages = (
            build_overview(player, 0, group='crafting')[0],
            build_profession(player, 'herbalism')[0],
            build_resource_list(player, 'herbalism', 0)[0],
            build_material(player, 'herb_magic', 0)[0],
            build_profession(player, 'blacksmith')[0],
            build_recipe(player, 'pe_sword_1h_01')[0],
            build_mutation_result(player, learned)[0],
            build_mutation_result(player, crafted, 'pe_sword_1h_01')[0],
            build_mutation_result(player, recovery)[0],
            *(build_mutation_result(player, receipt)[0] for receipt in failures),
        )
        combined = '\n'.join(stages)
        assert all(stage.strip() for stage in stages)
        assert '[professions.' not in combined
        assert not any(raw in combined for raw in (
            'missing_materials', 'profession_locked', 'stale_action',
            'ordinary_one', 'not_applicable', 'action_kind', 'profession_key',
        ))
        if lang != 'ru':
            assert not re.search('[А-Яа-яЁё]', combined)
