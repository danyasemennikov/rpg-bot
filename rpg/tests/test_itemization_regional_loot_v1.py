"""Contract coverage for Itemization, Regional Loot & Reliable Gear Progression V1."""

from __future__ import annotations

import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import pytest

from database import create_player, get_connection, get_player, init_db
from game.action_receipts import issue_actions
from game.equipment_stats import aggregate_equipped_stat_bonuses, get_player_effective_stats
from game.field_catalog import (
    ARMOR_BASE,
    ARMOR_SLOT_COEFFICIENTS,
    DRY_STREAK_INCREMENT_BY_SPAWN_PROFILE,
    FIELD_ARMOR_IDS,
    FIELD_DRY_STREAK_THRESHOLD,
    FIELD_ITEM_IDS,
    FIELD_ITEMS,
    FIELD_OFFHAND_IDS,
    FIELD_ROUTE_POOLS,
    FIELD_VENDOR_LOCATIONS,
    FIELD_WEAPON_IDS,
    GEAR_CHANCE_BY_SPAWN_PROFILE,
    RARITY_WEIGHTS_BY_SPAWN_PROFILE,
    choose_field_item,
    source_routes_for_item,
)
from game.gear_instances import (
    create_gear_instance,
    generate_secondary_rolls_for_item,
    get_equipped_gear_instances,
    grant_item_to_player,
    resolve_gear_instance_item_data,
)
from game.gear_progression import (
    apply_gear_intent,
    exchange_enhancement_crystal,
    get_equipment_goal,
    issue_crystal_exchange_intent,
    issue_gear_intent,
    set_equipment_goal,
)
from game.gear_ui import catalog_page, compare_instance_to_slot, get_field_source_manifest
from game.i18n import get_item_description, get_item_name
from game.items_data import get_item
from game.itemization import get_generated_secondary_pool_for_item, get_secondary_count_budget_for_rarity
from game.pve_live import create_pve_encounter, persist_solo_pve_encounter_state
from game.pve_reward_settlement import (
    _roll_unit_rewards,
    apply_prepared_settlement,
    get_settlement,
    list_legacy_review_reports,
    list_recent_reward_receipts,
    prepare_victory_settlement,
    recover_player_settlements,
    review_ambiguous_legacy_victories,
)
from game.reward_source_metadata import build_open_world_combat_source_metadata
from game.skills import get_available_skills, get_weapon_tree
from game.weapon_mastery import add_mastery_exp, get_mastery
from handlers.inventory import build_field_catalog, build_field_catalog_detail, build_gear_comparison
from handlers.location import (
    CURATED_EQUIPMENT_VENDOR_STOCK,
    build_craftsmen_advancement_detail,
    build_craftsmen_advancement_list,
    build_shop_message,
    try_buy_curated_shop_item,
)

PID = 919001


def make_player(player_id: int = PID, *, location: str = 'capital_city', gold: int = 100_000):
    create_player(player_id, f'p{player_id}', f'Player {player_id}', {
        'strength': 3, 'agility': 3, 'intuition': 2, 'vitality': 1, 'wisdom': 2, 'luck': 1,
    }, lang='en')
    conn = get_connection()
    conn.execute('UPDATE players SET location_id=?, gold=? WHERE telegram_id=?', (location, gold, player_id))
    conn.commit()
    conn.close()


def rows(sql: str, params=()):
    conn = get_connection()
    try:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def test_static_catalog_has_all_frozen_values_slots_profiles_and_locales():
    assert len(FIELD_ITEMS) == 32
    assert len(FIELD_WEAPON_IDS) == 10
    assert len(FIELD_ARMOR_IDS) == 15
    assert len(FIELD_OFFHAND_IDS) == 3
    assert len(FIELD_ITEM_IDS) == len(set(FIELD_ITEM_IDS))
    assert {item['slot_identity'] for item in FIELD_ITEMS.values()} == {
        'weapon', 'offhand', 'helmet', 'chest', 'legs', 'boots', 'gloves', 'ring', 'amulet'}
    expected_damage = {
        'field_sword_1h': (11, 16), 'field_sword_2h': (15, 22), 'field_axe_2h': (16, 24),
        'field_daggers': (8, 13), 'field_bow': (9, 15), 'field_magic_staff': (9, 14),
        'field_wand': (8, 12), 'field_holy_staff': (8, 13), 'field_holy_rod': (8, 12),
        'field_tome': (7, 11),
    }
    assert {item_id: (FIELD_ITEMS[item_id]['damage_min'], FIELD_ITEMS[item_id]['damage_max'])
            for item_id in FIELD_WEAPON_IDS} == expected_damage
    for item_id, item in FIELD_ITEMS.items():
        assert item['rarity'] == 'common' and item['req_level'] == 1 and item['sell_price'] == 5
        assert item['buy_price'] in {20, 40, 45, 60, 80}
        for lang in ('ru', 'en', 'es'):
            assert get_item_name(item_id, lang) != item_id
            assert get_item_description(item_id, lang)
    for armor_class, (base_defense, bonuses, _weight) in ARMOR_BASE.items():
        for slot, coefficient in ARMOR_SLOT_COEFFICIENTS.items():
            item = FIELD_ITEMS[f'field_{armor_class}_{slot}']
            assert item['defense'] == round(base_defense * coefficient)
            assert json.loads(item['stat_bonus_json']) == {
                key: round(value * coefficient) for key, value in bonuses.items() if round(value * coefficient)}
    for vendor in FIELD_VENDOR_LOCATIONS:
        assert set(FIELD_ITEM_IDS) <= {row['item_id'] for row in CURATED_EQUIPMENT_VENDOR_STOCK[vendor]}


def test_new_locale_keys_have_full_ru_en_es_parity_and_placeholders():
    from locales.en import STRINGS as en
    from locales.es import STRINGS as es
    from locales.ru import STRINGS as ru
    import string
    assert set(ru['gear']) == set(en['gear']) == set(es['gear'])
    formatter = string.Formatter()
    for key in ru['gear']:
        placeholders = []
        for strings in (ru, en, es):
            value = strings['gear'][key]
            placeholders.append({name for _, name, _, _ in formatter.parse(value) if name})
        assert placeholders[0] == placeholders[1] == placeholders[2], key


def test_regional_manifests_are_distinct_and_sources_are_real():
    assert len(FIELD_ROUTE_POOLS) == 5
    assert len({tuple(pool) for pool in FIELD_ROUTE_POOLS.values()}) == 5
    assert 'field_daggers' in FIELD_ROUTE_POOLS['route_westwild']
    assert 'field_shield' in FIELD_ROUTE_POOLS['route_frostspine']
    assert 'field_focus' in FIELD_ROUTE_POOLS['route_ashen_ruins']
    assert 'field_censer' in FIELD_ROUTE_POOLS['route_mireveil']
    assert 'field_holy_rod' in FIELD_ROUTE_POOLS['route_sunscar']
    for item_id in FIELD_ITEM_IDS:
        manifest = get_field_source_manifest(item_id)
        assert manifest['vendors'] == FIELD_VENDOR_LOCATIONS
        assert manifest['universal_routes'] == tuple(FIELD_ROUTE_POOLS)
        assert manifest['stub_key'] == 'starter_stubs'
        assert manifest['curated_routes'] == source_routes_for_item(item_id)
    for location in ('westwild_n1', 'frostspine_n1', 'ashen_n1', 'mireveil_n1', 'sunscar_n1'):
        meta = build_open_world_combat_source_metadata(source_id='forest_wolf', mob_level=2,
            source_category='open_world_normal', location_id=location, spawn_profile='normal')
        assert meta.open_world_region_identity


def test_pool_split_frequency_and_rarity_constants_are_frozen():
    assert GEAR_CHANCE_BY_SPAWN_PROFILE == {'normal': 0.08, 'elite': 0.35}
    assert DRY_STREAK_INCREMENT_BY_SPAWN_PROFILE == {'normal': 1, 'elite': 3}
    assert dict(RARITY_WEIGHTS_BY_SPAWN_PROFILE['normal']) == {'common': .70, 'uncommon': .28, 'rare': .02}
    assert dict(RARITY_WEIGHTS_BY_SPAWN_PROFILE['elite']) == {'uncommon': .70, 'rare': .295, 'epic': .005}
    import random
    rng = random.Random(991)
    draws = [choose_field_item('route_westwild', rng) in FIELD_ROUTE_POOLS['route_westwild'] for _ in range(30_000)]
    # Universal draws can also land in the curated pool; this lower bound proves
    # that the configured 80% regional branch is actually expressed.
    assert sum(draws) / len(draws) > .80
    universal_rng = random.Random(44)
    assert set(choose_field_item('starter_stubs', universal_rng) for _ in range(500)) - set(FIELD_ITEM_IDS) == set()


class NoGearRng:
    def random(self):
        return 0.99

    def randint(self, low, high):
        return low

    def choice(self, values):
        return list(values)[0]

    def sample(self, values, k):
        return list(values)[:k]


@pytest.mark.parametrize(('profile', 'before'), [('normal', 11), ('elite', 9)])
def test_exact_dry_streak_guarantee_transitions(profile, before):
    unit, after = _roll_unit_rewards(
        unit={'unit_id': 'u1', 'mob_id': 'contract_test_mob', 'spawn_profile': profile},
        fallback_mob={'id': 'contract_test_mob', 'level': 7, 'gold_min': 1, 'gold_max': 1,
                      'exp_reward': 2, 'loot_table': []},
        route_id='route_westwild', policy_version='field_loot_v1', dry_streak=before,
        rng=NoGearRng(), location_id='westwild_n1')
    assert unit['counter_before'] == before
    assert after == 0 and unit['counter_after'] == 0 and unit['guaranteed']
    assert len(unit['gear_specs']) == 1
    assert unit['gear_specs'][0]['rarity'] == 'uncommon'
    assert unit['gear_specs'][0]['guaranteed'] is True
    assert FIELD_DRY_STREAK_THRESHOLD == 12


def test_generated_affixes_use_existing_allowlist_and_exact_counts():
    import random
    item = FIELD_ITEMS['field_focus']
    for rarity, count in [('common', 0), ('uncommon', 1), ('rare', 2), ('epic', 3)]:
        rolls = generate_secondary_rolls_for_item(item, rarity=rarity, item_tier=10, rng=random.Random(8))
        assert len(rolls) == count == get_secondary_count_budget_for_rarity(rarity)
        assert {roll['stat'] for roll in rolls} <= set(get_generated_secondary_pool_for_item(item))


def test_all_ten_families_are_fixed_vendor_acquisitions_with_mastery_and_skills():
    make_player()
    start_gold = get_player(PID)['gold']
    acquired = []
    for item_id in FIELD_WEAPON_IDS:
        token = issue_actions(PID, 'shop_buy', [item_id])[item_id]
        result = try_buy_curated_shop_item(PID, 'capital_city', 1, item_id, action_token=token)
        assert result == {'ok': True, 'price': 45}
        instance = rows('SELECT * FROM gear_instances WHERE telegram_id=? AND base_item_id=?', (PID, item_id))[0]
        assert instance['item_tier'] == 1 and instance['rarity'] == 'common'
        assert json.loads(instance['secondary_rolls_json']) == []
        assert json.loads(instance['source_metadata_json'])['location_id'] == 'capital_city'
        family = FIELD_ITEMS[item_id]['weapon_profile']
        mastery = get_mastery(PID, item_id)
        assert mastery['weapon_id'] == family
        assert get_weapon_tree(family)
        assert get_available_skills(item_id, mastery['level'], family)
        acquired.append(family)
    assert len(set(acquired)) == 10
    assert get_player(PID)['gold'] == start_gold - 450


def test_numeric_diagnostic_all_ten_field_families_beat_starter_target_with_twelve_points():
    from game.combat_simulation import (
        SimulationConfig, build_simulation_mob_preset, build_simulation_player_preset, simulate_single_combat)

    mob = build_simulation_mob_preset('forest_wolf')
    for item_id in FIELD_WEAPON_IDS:
        item = FIELD_ITEMS[item_id]
        stats = {key: 1 for key in ('strength', 'agility', 'intuition', 'vitality', 'wisdom', 'luck')}
        primary = next(key.removeprefix('req_') for key, value in item.items()
                       if key.startswith('req_') and value == 3)
        stats[primary] = 7
        assert sum(stats.values()) == 12
        player = build_simulation_player_preset(
            **stats,
            weapon_damage=round((item['damage_min'] + item['damage_max']) / 2),
            weapon_type=item['weapon_type'], weapon_profile=item['weapon_profile'],
            damage_school=item['damage_school'],
        )
        outcomes = [simulate_single_combat(player, mob, config=SimulationConfig(seed=seed, max_turns=40)).winner
                    for seed in range(10)]
        assert set(outcomes) == {'player'}, (item_id, outcomes)


def test_shop_and_catalog_ui_are_bounded_preview_driven_and_callbacks_fit():
    make_player()
    player = dict(get_player(PID))
    text, keyboard = build_shop_message(player, {'id': 'capital_city'})
    item_rows = [row for row in keyboard.inline_keyboard if row and row[0].callback_data.startswith('shop_preview_')]
    assert len(item_rows) <= 8 and len(text) <= 4096
    catalog_text, catalog_keyboard = build_field_catalog(player, 'armor', 0)
    catalog_rows = [row for row in catalog_keyboard.inline_keyboard if row and row[0].callback_data.startswith('inv_citem_')]
    assert len(catalog_rows) == 8 and len(catalog_text) <= 4096
    for row in keyboard.inline_keyboard + catalog_keyboard.inline_keyboard:
        for button in row:
            assert len(button.callback_data.encode()) <= 64
    detail_text, detail_keyboard = build_field_catalog_detail(player, 'field_sword_1h', 'weapon', 0)
    assert '45' in detail_text and 'Karn' in detail_text
    assert any(button.callback_data.startswith('shop_buy_field_sword_1h|')
               for row in detail_keyboard.inline_keyboard for button in row)


def test_base_defense_once_all_armor_slots_and_instance_first_deduplication():
    make_player()
    expected_defense = 0
    for slot in ('helmet', 'chest', 'legs', 'boots', 'gloves'):
        item_id = f'field_heavy_{slot}'
        instance_id = create_gear_instance(PID, item_id)
        conn = get_connection()
        conn.execute('UPDATE gear_instances SET equipped_slot=? WHERE id=?', (slot, instance_id))
        conn.commit(); conn.close()
        expected_defense += FIELD_ITEMS[item_id]['defense']
    shield = create_gear_instance(PID, 'field_shield')
    conn = get_connection()
    legacy = conn.execute("SELECT id FROM inventory WHERE telegram_id=? AND item_id='wooden_sword'", (PID,)).fetchone()
    if not legacy:
        conn.execute("INSERT INTO inventory(telegram_id,item_id,quantity) VALUES (?, 'iron_shield', 1)", (PID,))
        legacy_id = conn.execute('SELECT last_insert_rowid() AS id').fetchone()['id']
    else:
        legacy_id = legacy['id']
    conn.execute('UPDATE equipment SET offhand=? WHERE telegram_id=?', (legacy_id, PID))
    conn.execute("UPDATE gear_instances SET equipped_slot='offhand' WHERE id=?", (shield,))
    conn.commit(); conn.close()
    bonuses = aggregate_equipped_stat_bonuses(PID)
    assert bonuses['physical_defense'] == expected_defense + 4
    assert bonuses['max_hp'] == sum(json.loads(FIELD_ITEMS[f'field_heavy_{slot}']['stat_bonus_json']).get('max_hp', 0)
                                    for slot in ('helmet', 'chest', 'legs', 'boots', 'gloves')) + 8


def test_ring_comparison_targets_either_slot_and_reports_real_deltas():
    make_player()
    equipped = create_gear_instance(PID, 'field_guard_ring')
    candidate = create_gear_instance(PID, 'field_precision_ring')
    conn = get_connection()
    conn.execute("UPDATE gear_instances SET equipped_slot='ring1' WHERE id=?", (equipped,))
    conn.commit(); conn.close()
    ring1 = compare_instance_to_slot(PID, candidate, 'ring1')
    ring2 = compare_instance_to_slot(PID, candidate, 'ring2')
    text, _ = build_gear_comparison(PID, f'g{candidate}', 'ring1', 'accessory', 'en')
    before = get_player_effective_stats(PID, dict(get_player(PID)))
    token = issue_gear_intent(PID, 'equip', candidate, target_slot='ring1')
    assert apply_gear_intent(PID, 'equip', token)['status'] == 'equipped'
    after = get_player_effective_stats(PID, dict(get_player(PID)))
    assert ring1['deltas']['max_hp'] == after['max_hp'] - before['max_hp'] == -26
    assert ring1['deltas']['physical_defense'] == (
        after['effective_physical_defense'] - before['effective_physical_defense'])
    assert ring1['deltas']['accuracy'] == after['accuracy_bonus'] - before['accuracy_bonus'] == 2
    assert ring2['current_item_id'] is None and ring2['deltas']['accuracy'] == 2
    assert 'Accuracy' in text and 'Max HP' in text and 'better' not in text.lower()


def test_revision_bound_equip_enhance_sale_and_travel_staleness_are_atomic():
    make_player()
    instance_id = create_gear_instance(PID, 'field_sword_1h')
    equip_token = issue_gear_intent(PID, 'equip', instance_id, target_slot='weapon')
    assert apply_gear_intent(PID, 'equip', equip_token)['status'] == 'equipped'
    assert apply_gear_intent(PID, 'equip', equip_token)['status'] == 'stale_action'
    assert get_equipped_gear_instances(PID)['weapon']['id'] == instance_id

    conn = get_connection()
    conn.execute("INSERT INTO inventory(telegram_id,item_id,quantity) VALUES (?, 'enhance_shard', 2)", (PID,))
    conn.commit(); conn.close()
    enhance_token = issue_gear_intent(PID, 'enhance', instance_id)
    first = apply_gear_intent(PID, 'enhance', enhance_token, rng_roll=0.0)
    assert first['status'] == 'enhanced' and first['after'] == 1
    assert apply_gear_intent(PID, 'enhance', enhance_token, rng_roll=0.0)['status'] == 'stale_action'

    unequip_token = issue_gear_intent(PID, 'unequip', instance_id, target_slot='weapon')
    assert apply_gear_intent(PID, 'unequip', unequip_token)['status'] == 'unequipped'
    sale_token = issue_gear_intent(PID, 'sale', instance_id)
    before_gold = get_player(PID)['gold']
    with pytest.raises(RuntimeError):
        apply_gear_intent(PID, 'sale', sale_token, failure_hook=lambda point: (_ for _ in ()).throw(RuntimeError(point)))
    assert rows('SELECT id FROM gear_instances WHERE id=?', (instance_id,))
    assert get_player(PID)['gold'] == before_gold
    sold = apply_gear_intent(PID, 'sale', sale_token)
    assert sold['status'] == 'sold' and sold['gold'] == 5
    assert apply_gear_intent(PID, 'sale', sale_token)['status'] == 'stale_action'

    stale_instance = create_gear_instance(PID, 'field_bow')
    stale_token = issue_gear_intent(PID, 'sale', stale_instance)
    conn = get_connection()
    conn.execute('UPDATE players SET travel_revision=travel_revision+2 WHERE telegram_id=?', (PID,))
    conn.commit(); conn.close()
    assert apply_gear_intent(PID, 'sale', stale_token)['status'] == 'stale_action'


def test_foreign_busy_and_pending_pvp_intents_do_not_mutate():
    make_player()
    make_player(PID + 1)
    instance_id = create_gear_instance(PID, 'field_bow')
    token = issue_gear_intent(PID, 'sale', instance_id)
    assert apply_gear_intent(PID + 1, 'sale', token)['status'] == 'stale_action'
    conn = get_connection()
    conn.execute('''INSERT INTO pvp_engagements(attacker_id,defender_id,location_id,engagement_started_at,
        engagement_ready_at,engagement_state) VALUES (?,?,?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,'pending')''',
        (PID, PID + 1, 'capital_city'))
    conn.commit(); conn.close()
    assert apply_gear_intent(PID, 'sale', token)['status'] == 'in_battle'
    assert rows('SELECT id FROM gear_instances WHERE id=?', (instance_id,))


def test_equipment_cap_clamp_failure_rolls_back_token_and_equip(monkeypatch):
    from game import equipment_stats

    make_player()
    instance_id = create_gear_instance(PID, 'field_guard_ring')
    token = issue_gear_intent(PID, 'equip', instance_id, target_slot='ring1')
    original = equipment_stats.clamp_player_resources_to_effective_caps

    def fail_clamp(*_args, **_kwargs):
        raise RuntimeError('clamp_failure')

    monkeypatch.setattr(equipment_stats, 'clamp_player_resources_to_effective_caps', fail_clamp)
    with pytest.raises(RuntimeError, match='clamp_failure'):
        apply_gear_intent(PID, 'equip', token)
    assert rows('SELECT equipped_slot FROM gear_instances WHERE id=?', (instance_id,))[0]['equipped_slot'] is None
    assert rows('SELECT used FROM player_ui_actions WHERE token=?', (token,))[0]['used'] == 0

    monkeypatch.setattr(equipment_stats, 'clamp_player_resources_to_effective_caps', original)
    assert apply_gear_intent(PID, 'equip', token)['status'] == 'equipped'


def test_wrong_slot_requirements_materials_equipped_sale_and_active_pve_fail_closed():
    make_player(gold=0)
    sword = create_gear_instance(PID, 'field_sword_1h')
    wrong = issue_gear_intent(PID, 'equip', sword, target_slot='offhand')
    assert apply_gear_intent(PID, 'equip', wrong)['status'] == 'wrong_equipment_slot'
    conn = get_connection()
    conn.execute('UPDATE players SET strength=1, gold=100000 WHERE telegram_id=?', (PID,))
    conn.commit(); conn.close()
    token = issue_gear_intent(PID, 'equip', sword, target_slot='weapon')
    assert apply_gear_intent(PID, 'equip', token)['status'] == 'equipment_requirements'
    conn = get_connection(); conn.execute('UPDATE players SET strength=3 WHERE telegram_id=?', (PID,)); conn.commit(); conn.close()
    token = issue_gear_intent(PID, 'enhance', sword)
    assert apply_gear_intent(PID, 'enhance', token)['status'] == 'no_material'
    token = issue_gear_intent(PID, 'equip', sword, target_slot='weapon')
    assert apply_gear_intent(PID, 'equip', token)['status'] == 'equipped'
    token = issue_gear_intent(PID, 'sale', sword)
    assert apply_gear_intent(PID, 'sale', token)['status'] == 'equipped_item'

    spare = create_gear_instance(PID, 'field_bow')
    sale_token = issue_gear_intent(PID, 'sale', spare)
    battle = {'pve_encounter_id': 'busy-pve', 'mob_id': 'contract_test_mob', 'mob_dead': False}
    create_pve_encounter(owner_player_id=PID, side_a_player_ids=[PID], battle_state=battle,
                         mob={'id': 'contract_test_mob'}, encounter_id='busy-pve', location_id='capital_city')
    assert apply_gear_intent(PID, 'sale', sale_token)['status'] == 'in_battle'
    assert rows('SELECT id FROM gear_instances WHERE id=?', (spare,))


def test_changed_or_transferred_instance_and_competing_intents_are_stale():
    make_player()
    make_player(PID + 1)
    instance_id = create_gear_instance(PID, 'field_focus')
    first = issue_gear_intent(PID, 'sale', instance_id)
    second = issue_gear_intent(PID, 'sale', instance_id)
    # issue_actions replaces the previous menu for this kind.
    assert apply_gear_intent(PID, 'sale', first)['status'] == 'stale_action'
    conn = get_connection()
    conn.execute('UPDATE gear_instances SET telegram_id=?, revision=revision+1 WHERE id=?', (PID + 1, instance_id))
    conn.execute('UPDATE players SET gear_revision=gear_revision+1 WHERE telegram_id IN (?,?)', (PID, PID + 1))
    conn.commit(); conn.close()
    assert apply_gear_intent(PID, 'sale', second)['status'] == 'stale_action'


def test_tier_advancement_preserves_instance_identity_rolls_enhancement_and_durability():
    make_player()
    rolls = [{'stat': 'strength', 'value': 2}]
    instance_id = create_gear_instance(PID, 'field_sword_1h', rarity='uncommon',
        secondary_rolls_json=json.dumps(rolls), enhance_level=2, durability=73, max_durability=91)
    grant_item_to_player(PID, 'enhancement_crystal', 4)
    token = issue_gear_intent(PID, 'advance', instance_id)
    result = apply_gear_intent(PID, 'advance', token)
    assert result['status'] == 'advanced' and result['after'] == 5
    instance = rows('SELECT * FROM gear_instances WHERE id=?', (instance_id,))[0]
    assert instance['id'] == instance_id and instance['base_item_id'] == 'field_sword_1h'
    assert instance['rarity'] == 'uncommon' and json.loads(instance['secondary_rolls_json']) == rolls
    assert instance['enhance_level'] == 2 and instance['durability'] == 73 and instance['max_durability'] == 91
    detail, _ = build_craftsmen_advancement_detail(dict(get_player(PID)), instance_id)
    assert 'Tier 5' in detail and '→ 10' in detail
    listing, keyboard = build_craftsmen_advancement_list(dict(get_player(PID)))
    assert len(listing) <= 4096 and sum(1 for row in keyboard.inline_keyboard if 'advance_item' in row[0].callback_data) <= 8


def test_homecoming_shard_bridge_is_atomic_single_use_and_no_profession_xp():
    make_player()
    grant_item_to_player(PID, 'enhance_shard', 10)
    token = issue_crystal_exchange_intent(PID)
    assert exchange_enhancement_crystal(PID, token)['status'] == 'chapter_required'
    conn = get_connection()
    conn.execute("INSERT INTO player_contract_history(player_id,contract_key) VALUES (?, 'chapter_homecoming')", (PID,))
    conn.commit(); conn.close()
    before_professions = rows('SELECT * FROM player_crafting_professions WHERE player_id=?', (PID,))
    token = issue_crystal_exchange_intent(PID)
    before_gold = get_player(PID)['gold']
    assert exchange_enhancement_crystal(PID, token)['status'] == 'exchanged'
    assert exchange_enhancement_crystal(PID, token)['status'] == 'stale_action'
    assert get_player(PID)['gold'] == before_gold - 25
    assert rows("SELECT quantity FROM inventory WHERE telegram_id=? AND item_id='enhancement_crystal'", (PID,))[0]['quantity'] == 1
    assert rows('SELECT * FROM player_crafting_professions WHERE player_id=?', (PID,)) == before_professions


def make_terminal_encounter(player_id: int, encounter_id: str, *, location='westwild_n1', units=1,
                            participant_ids: list[int] | None = None):
    roster = participant_ids or [player_id]
    battle = {
        'pve_encounter_id': encounter_id, 'mob_id': 'contract_test_mob', 'mob_dead': True,
        'mob_hp': 0, 'location_id': location, 'weapon_id': 'field_sword_1h',
        'side_a_player_ids': roster,
        'participant_states': {
            str(roster_player_id): {
                'player_dead': False, 'defeated': False, 'player_hp': 10, 'hp': 10,
                'weapon_id': 'field_sword_1h',
            }
            for roster_player_id in roster
        },
        'enemy_units': [
            {'unit_id': f'u{i}', 'mob_id': 'contract_test_mob', 'spawn_profile': 'normal',
             'dead': True, 'hp': 0}
            for i in range(units)
        ],
    }
    mob = {'id': 'contract_test_mob', 'level': 7, 'exp_reward': 9, 'gold_min': 3, 'gold_max': 3, 'loot_table': []}
    create_pve_encounter(owner_player_id=player_id, side_a_player_ids=roster, battle_state=battle,
                         mob=mob, encounter_id=encounter_id, location_id=location)
    persist_solo_pve_encounter_state(encounter_id=encounter_id, battle_state=battle, mob=mob)
    return battle, mob


def settlement_snapshot(encounter_id: str, player_id: int):
    return {
        'player': rows('SELECT * FROM players WHERE telegram_id=?', (player_id,)),
        'inventory': rows('SELECT * FROM inventory WHERE telegram_id=? ORDER BY id', (player_id,)),
        'gear': rows('SELECT * FROM gear_instances WHERE telegram_id=? ORDER BY id', (player_id,)),
        'progress': rows('SELECT * FROM player_gear_progress WHERE player_id=? ORDER BY route_id', (player_id,)),
        'objectives': rows('SELECT * FROM player_contract_objectives WHERE player_id=? ORDER BY 1,2,3', (player_id,)),
        'mastery': rows('SELECT * FROM weapon_mastery WHERE telegram_id=? ORDER BY weapon_id', (player_id,)),
        'encounter': rows('SELECT * FROM pve_encounters WHERE encounter_id=?', (encounter_id,)),
        'participants': rows('SELECT * FROM pve_encounter_participants WHERE encounter_id=? ORDER BY player_id', (encounter_id,)),
        'settlement': rows('SELECT * FROM pve_reward_settlements WHERE encounter_id=?', (encounter_id,)),
    }


def test_two_transaction_settlement_guarantee_receipt_and_restart_idempotency(monkeypatch):
    make_player(location='westwild_n1')
    encounter_id = 'settlement-guarantee'
    battle, mob = make_terminal_encounter(PID, encounter_id)
    conn = get_connection()
    conn.execute("INSERT INTO player_gear_progress(player_id,route_id,dry_streak) VALUES (?, 'route_westwild', 11)", (PID,))
    conn.commit(); conn.close()
    monkeypatch.setitem(GEAR_CHANCE_BY_SPAWN_PROFILE, 'normal', 0.0)
    before_player = dict(get_player(PID))
    prepared = prepare_victory_settlement(encounter_id=encounter_id, battle_state=battle, mob=mob)
    assert prepared['status'] == 'prepared'
    assert dict(get_player(PID)) == before_player
    assert get_settlement(encounter_id)['status'] == 'prepared'
    applied = apply_prepared_settlement(encounter_id)
    assert applied['status'] == 'applied' and not applied['already_applied']
    recipient = applied['result']['recipients'][0]
    assert recipient['exp'] == 9 and recipient['gold'] == 3 and recipient['guaranteed']
    assert recipient['gear'][0]['rarity'] == 'uncommon'
    assert rows("SELECT dry_streak FROM player_gear_progress WHERE player_id=? AND route_id='route_westwild'", (PID,))[0]['dry_streak'] == 0
    after = settlement_snapshot(encounter_id, PID)
    retry = apply_prepared_settlement(encounter_id)
    assert retry['already_applied'] and settlement_snapshot(encounter_id, PID) == after
    assert len(list_recent_reward_receipts(PID)) == 1
    assert recover_player_settlements(PID)['recovered'] == []


@pytest.mark.parametrize('failure_point', [
    'after_xp_update', 'after_gold_update', 'after_first_gear_instance', 'after_counter_update',
    'after_contract_progress', 'after_mastery_award', 'before_final_encounter_update',
])
def test_t2_failure_injection_rolls_back_every_related_write(monkeypatch, failure_point):
    player_id = PID + 100 + hash(failure_point) % 10_000
    make_player(player_id, location='westwild_n1')
    encounter_id = f'failure-{failure_point}'
    battle, mob = make_terminal_encounter(player_id, encounter_id)
    conn = get_connection()
    conn.execute("INSERT INTO player_gear_progress(player_id,route_id,dry_streak) VALUES (?, 'route_westwild', 11)", (player_id,))
    conn.commit(); conn.close()
    monkeypatch.setitem(GEAR_CHANCE_BY_SPAWN_PROFILE, 'normal', 0.0)
    prepare_victory_settlement(encounter_id=encounter_id, battle_state=battle, mob=mob)
    before = settlement_snapshot(encounter_id, player_id)
    def fail(point):
        if point == failure_point:
            raise RuntimeError(point)
    with pytest.raises(RuntimeError, match=failure_point):
        apply_prepared_settlement(encounter_id, failure_hook=fail)
    assert settlement_snapshot(encounter_id, player_id) == before
    assert apply_prepared_settlement(encounter_id)['status'] == 'applied'


def test_competing_settlement_requests_apply_once(monkeypatch):
    make_player(location='westwild_n1')
    battle, mob = make_terminal_encounter(PID, 'settlement-contention')
    monkeypatch.setitem(GEAR_CHANCE_BY_SPAWN_PROFILE, 'normal', 0.0)
    prepare_victory_settlement(encounter_id='settlement-contention', battle_state=battle, mob=mob)
    before = dict(get_player(PID))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _index: apply_prepared_settlement('settlement-contention'), range(2)))
    assert [result['status'] for result in results] == ['applied', 'applied']
    assert sorted(bool(result.get('already_applied')) for result in results) == [False, True]
    after = dict(get_player(PID))
    assert after['exp'] - before['exp'] == 9 and after['gold'] - before['gold'] == 3
    assert len(list_recent_reward_receipts(PID)) == 1


def test_t1_and_post_commit_failure_semantics(monkeypatch):
    make_player(location='westwild_n1')
    battle, mob = make_terminal_encounter(PID, 't1-failure')
    with pytest.raises(RuntimeError, match='before_t1_commit'):
        prepare_victory_settlement(encounter_id='t1-failure', battle_state=battle, mob=mob,
            failure_hook=lambda point: (_ for _ in ()).throw(RuntimeError(point)) if point == 'before_t1_commit' else None)
    assert get_settlement('t1-failure') is None
    assert rows("SELECT status FROM pve_encounters WHERE encounter_id='t1-failure'")[0]['status'] == 'active'
    with pytest.raises(RuntimeError, match='after_t1_commit'):
        prepare_victory_settlement(encounter_id='t1-failure', battle_state=battle, mob=mob,
            failure_hook=lambda point: (_ for _ in ()).throw(RuntimeError(point)) if point == 'after_t1_commit' else None)
    assert get_settlement('t1-failure')['status'] == 'prepared'
    before = dict(get_player(PID))
    with pytest.raises(RuntimeError, match='after_t2_commit'):
        apply_prepared_settlement('t1-failure', failure_hook=lambda point: (_ for _ in ()).throw(RuntimeError(point)) if point == 'after_t2_commit' else None)
    after = dict(get_player(PID))
    assert after != before
    snapshot = settlement_snapshot('t1-failure', PID)
    assert apply_prepared_settlement('t1-failure')['already_applied']
    assert settlement_snapshot('t1-failure', PID) == snapshot


def test_stackable_and_upgrade_deduction_failure_points_roll_back():
    make_player(location='westwild_n1')
    encounter_id = 'stackable-failure'
    battle, mob = make_terminal_encounter(PID, encounter_id)
    mob['loot_table'] = [('wolf_pelt', 1.0)]
    persist_solo_pve_encounter_state(encounter_id=encounter_id, battle_state=battle, mob=mob)
    prepare_victory_settlement(encounter_id=encounter_id, battle_state=battle, mob=mob)
    before = settlement_snapshot(encounter_id, PID)
    with pytest.raises(RuntimeError, match='after_first_stackable_grant'):
        apply_prepared_settlement(encounter_id, failure_hook=lambda point: (_ for _ in ()).throw(RuntimeError(point))
                                  if point == 'after_first_stackable_grant' else None)
    assert settlement_snapshot(encounter_id, PID) == before

    mutation_player = PID + 1
    make_player(mutation_player)
    instance_id = create_gear_instance(mutation_player, 'field_bow')
    grant_item_to_player(mutation_player, 'enhance_shard', 1)
    token = issue_gear_intent(mutation_player, 'enhance', instance_id)
    before_gold = get_player(mutation_player)['gold']
    with pytest.raises(RuntimeError, match='after_material_deduction'):
        apply_gear_intent(mutation_player, 'enhance', token, rng_roll=0.0,
                          failure_hook=lambda point: (_ for _ in ()).throw(RuntimeError(point)))
    assert get_player(mutation_player)['gold'] == before_gold
    assert rows("SELECT quantity FROM inventory WHERE telegram_id=? AND item_id='enhance_shard'", (mutation_player,))[0]['quantity'] == 1
    assert rows('SELECT enhance_level FROM gear_instances WHERE id=?', (instance_id,))[0]['enhance_level'] == 0


def test_nonterminal_unknown_policy_and_duplicate_callbacks_fail_closed():
    make_player(location='westwild_n1')
    battle, mob = make_terminal_encounter(PID, 'invalid-terminal')
    battle['mob_dead'] = False
    assert prepare_victory_settlement(encounter_id='invalid-terminal', battle_state=battle, mob=mob)['status'] == 'invalid_outcome'
    assert get_settlement('invalid-terminal') is None
    battle['mob_dead'] = True
    conn = get_connection()
    conn.execute("UPDATE pve_encounters SET reward_policy_version='unknown_v99' WHERE encounter_id='invalid-terminal'")
    conn.commit(); conn.close()
    with pytest.raises(ValueError, match='unknown_reward_policy'):
        prepare_victory_settlement(encounter_id='invalid-terminal', battle_state=battle, mob=mob)
    assert get_settlement('invalid-terminal') is None


def test_group_settlement_excludes_defeated_participant_and_preserves_personal_rewards(monkeypatch):
    make_player(location='westwild_n1')
    make_player(PID + 1, location='westwild_n1')
    battle, mob = make_terminal_encounter(
        PID, 'group-settlement', units=2, participant_ids=[PID, PID + 1])
    conn = get_connection()
    conn.execute("UPDATE pve_encounter_participants SET status='defeated' WHERE encounter_id='group-settlement' AND player_id=?", (PID + 1,))
    conn.execute('UPDATE players SET in_battle=1 WHERE telegram_id IN (?,?)', (PID, PID + 1))
    conn.commit(); conn.close()
    battle['participant_states'][str(PID + 1)] = {
        'player_dead': True, 'defeated': True, 'player_hp': 0, 'hp': 0,
        'weapon_id': 'field_bow',
    }
    battle['side_a_player_ids'] = [PID]
    persist_solo_pve_encounter_state(
        encounter_id='group-settlement', battle_state=battle, mob=mob)
    before_defeated = dict(get_player(PID + 1))
    monkeypatch.setitem(GEAR_CHANCE_BY_SPAWN_PROFILE, 'normal', 0.0)
    prepare_victory_settlement(encounter_id='group-settlement', battle_state=battle, mob=mob)
    result = apply_prepared_settlement('group-settlement')['result']
    assert [row['player_id'] for row in result['recipients']] == [PID]
    defeated_after = dict(get_player(PID + 1))
    assert defeated_after['exp'] == before_defeated['exp'] and defeated_after['gold'] == before_defeated['gold']
    assert not rows('SELECT * FROM player_gear_progress WHERE player_id=?', (PID + 1,))


def test_legacy_resolving_victory_is_quarantined_without_replay_and_lock_is_safe():
    make_player(location='westwild_n1')
    battle, mob = make_terminal_encounter(PID, 'legacy-ambiguous')
    conn = get_connection()
    conn.execute("UPDATE pve_encounters SET status='resolving_victory' WHERE encounter_id='legacy-ambiguous'")
    conn.execute('UPDATE players SET in_battle=1 WHERE telegram_id=?', (PID,))
    before = dict(get_player(PID))
    conn.commit(); conn.close()
    assert review_ambiguous_legacy_victories() == 1
    settlement = get_settlement('legacy-ambiguous')
    assert settlement['status'] == 'legacy_review'
    assert settlement['plan']['reason'] == 'ambiguous_pre_v1_resolving_victory'
    after = dict(get_player(PID))
    assert after['exp'] == before['exp'] and after['gold'] == before['gold'] and after['in_battle'] == 0
    recovery = recover_player_settlements(PID)
    assert recovery['legacy_review'] == ['legacy-ambiguous'] and recovery['recovered'] == []
    report = list_legacy_review_reports(PID)[0]
    assert report['encounter_id'] == 'legacy-ambiguous'
    assert report['automatic_replay'] is False
    assert report['compensation_requires_owner_decision'] is True
    assert report['evidence']['status'] == 'resolving_victory'


def test_pre_upgrade_active_encounter_keeps_legacy_policy_and_unknown_item_fallback():
    make_player(location='westwild_n1')
    battle, mob = make_terminal_encounter(PID, 'legacy-active')
    mob['loot_table'] = [('iron_sword', 1.0)]
    conn = get_connection()
    conn.execute("UPDATE pve_encounters SET reward_policy_version='legacy_v0', mob_json=? WHERE encounter_id='legacy-active'",
                 (json.dumps(mob),))
    conn.execute('''INSERT INTO items(item_id,name,description,item_type,rarity,buy_price,sell_price)
        VALUES ('retired_relic','Retired relic','Preserved legacy row','material','rare',0,1)''')
    conn.commit(); conn.close()
    prepared = prepare_victory_settlement(encounter_id='legacy-active', battle_state=battle, mob=mob)
    assert prepared['plan']['policy_version'] == 'legacy_v0'
    gear_specs = [spec for recipient in prepared['plan']['recipients'] for unit in recipient['units']
                  for spec in unit['gear_specs']]
    assert [spec['base_item_id'] for spec in gear_specs] == ['iron_sword']
    assert get_item('retired_relic')['description'] == 'Preserved legacy row'


def test_migration_is_idempotent_and_preserves_existing_instance_fields():
    make_player()
    instance_id = create_gear_instance(PID, 'field_focus', item_tier=10, rarity='rare',
        secondary_rolls_json='[{"stat":"wisdom","value":2}]', enhance_level=4, durability=67, max_durability=88)
    before = rows('SELECT * FROM gear_instances WHERE id=?', (instance_id,))[0]
    init_db(); init_db()
    after = rows('SELECT * FROM gear_instances WHERE id=?', (instance_id,))[0]
    assert after == before
    assert get_equipment_goal(PID) is None
    assert not rows('SELECT * FROM player_gear_progress WHERE player_id=?', (PID,))
    assert not rows('PRAGMA foreign_key_check')


def test_goal_is_single_replaceable_navigation_state_and_does_not_modify_rng():
    make_player()
    assert set_equipment_goal(PID, 'field_bow') and get_equipment_goal(PID) == 'field_bow'
    assert set_equipment_goal(PID, 'field_focus') and get_equipment_goal(PID) == 'field_focus'
    assert not set_equipment_goal(PID, 'iron_sword')
    assert set_equipment_goal(PID, None) and get_equipment_goal(PID) is None


def test_tier_and_enhancement_strengthen_same_resolved_instance():
    make_player()
    instance_id = create_gear_instance(PID, 'field_focus')
    base = resolve_gear_instance_item_data(rows('SELECT * FROM gear_instances WHERE id=?', (instance_id,))[0])
    conn = get_connection()
    conn.execute('UPDATE gear_instances SET item_tier=5, enhance_level=1 WHERE id=?', (instance_id,))
    conn.commit(); conn.close()
    upgraded = resolve_gear_instance_item_data(rows('SELECT * FROM gear_instances WHERE id=?', (instance_id,))[0])
    assert upgraded['instance_id'] == base['instance_id']
    assert upgraded['defense'] > base['defense'] or upgraded['resolved_stat_bonus'] != base['resolved_stat_bonus']
