from __future__ import annotations

import json

from database import get_connection, get_player
from game.action_receipts import issue_actions
from game.build_contract import MASTERY_MODEL_VERSION
from game.build_progression import (
    apply_attribute_redistribution,
    apply_family_reset,
    apply_skill_purchase,
    attribute_redistribution_preview,
    build_migration_audit,
    issue_family_reset_intent,
    issue_skill_purchase_intent,
    migrate_character_builds_v1,
)
from game.gear_instances import get_equipped_gear_instances
from game.gear_progression import apply_gear_intent, issue_gear_intent
from handlers.location import try_buy_curated_shop_item


def _rows(sql: str, args: tuple = ()) -> list[dict]:
    conn = get_connection()
    try:
        return [dict(row) for row in conn.execute(sql, args)]
    finally:
        conn.close()


def _buy_and_equip_bow() -> int:
    token = issue_actions(1, 'shop_buy', ['field_bow'])['field_bow']
    result = try_buy_curated_shop_item(
        1, 'capital_city', 1, 'field_bow', action_token=token,
    )
    assert result == {'ok': True, 'price': 45}
    instance = _rows(
        "SELECT * FROM gear_instances WHERE telegram_id=1 AND base_item_id='field_bow'",
    )[0]
    assert json.loads(instance['source_metadata_json']) == {
        'location_id': 'capital_city', 'source': 'vendor',
    }
    intent = issue_gear_intent(1, 'equip', instance['id'], target_slot='weapon')
    assert apply_gear_intent(1, 'equip', intent)['status'] == 'equipped'
    return int(instance['id'])


def _set_m8_bow_budget() -> None:
    conn = get_connection()
    conn.execute(
        '''INSERT OR REPLACE INTO weapon_mastery
           (telegram_id,weapon_id,level,exp,skill_points,model_version)
           VALUES (1,'bow',8,0,9,?)''',
        (MASTERY_MODEL_VERSION,),
    )
    conn.commit()
    conn.close()


def _learn(skill_id: str) -> dict:
    issued = issue_skill_purchase_intent(1, 'bow', skill_id)
    assert issued['legal'] is True
    result = apply_skill_purchase(1, issued['token'])
    assert result['success'] is True
    return result


def test_safe_hub_reset_switches_sibling_without_losing_mastery_or_points():
    migrate_character_builds_v1()
    instance_id = _buy_and_equip_bow()
    _set_m8_bow_budget()
    _learn('hunters_mark')
    _learn('aimed_shot')

    issued = issue_family_reset_intent(1, 'bow')
    assert issued['refund'] == 2
    first = apply_family_reset(1, issued['token'])
    duplicate = apply_family_reset(1, issued['token'])
    assert first == {
        'success': True, 'op': 'reset_family', 'family': 'bow', 'refunded': 2,
    }
    assert duplicate['already_applied'] is True
    mastery = _rows(
        "SELECT level,exp,skill_points FROM weapon_mastery WHERE telegram_id=1 AND weapon_id='bow'",
    )[0]
    assert mastery == {'level': 8, 'exp': 0, 'skill_points': 9}
    assert not _rows(
        "SELECT * FROM player_skills WHERE telegram_id=1 AND skill_id IN ('hunters_mark','aimed_shot')",
    )

    _learn('quick_shot')
    after = _rows(
        "SELECT level,exp,skill_points FROM weapon_mastery WHERE telegram_id=1 AND weapon_id='bow'",
    )[0]
    assert after == {'level': 8, 'exp': 0, 'skill_points': 8}
    assert get_equipped_gear_instances(1)['weapon']['id'] == instance_id
    assert build_migration_audit() == {
        'family_invariant_failures': [], 'attribute_invariant_failures': [],
    }


def test_redistribution_names_unequip_clamps_resources_and_preserves_item_ledger():
    migrate_character_builds_v1()
    instance_id = _buy_and_equip_bow()
    conn = get_connection()
    conn.execute('UPDATE players SET hp=77,mana=33 WHERE telegram_id=1')
    conn.commit()
    conn.close()
    proposed = {
        'strength': 1, 'agility': 1, 'intuition': 1,
        'vitality': 20, 'wisdom': 1, 'luck': 1,
    }
    preview = attribute_redistribution_preview(1, proposed)
    assert preview['success'] is True
    assert preview['unequips'] == [{
        'slot': 'weapon', 'instance_id': instance_id,
        'item_id': 'field_bow', 'name': 'field_bow',
    }]
    result = apply_attribute_redistribution(1, preview['token'])
    assert result['success'] is True
    assert result['unequipped'] == preview['unequips']
    player = dict(get_player(1))
    assert player['hp'] == 77 and player['mana'] == 33
    assert player['max_hp'] == 460 and player['max_mana'] == 62
    item = _rows('SELECT * FROM gear_instances WHERE id=?', (instance_id,))[0]
    assert item['equipped_slot'] is None
    assert item['telegram_id'] == 1 and item['base_item_id'] == 'field_bow'


def test_old_message_travel_and_battle_races_cannot_overwrite_build_authority():
    migrate_character_builds_v1()
    _set_m8_bow_budget()

    old = issue_skill_purchase_intent(1, 'bow', 'quick_shot')
    current = issue_skill_purchase_intent(1, 'bow', 'quick_shot')
    assert apply_skill_purchase(1, old['token']) == {
        'success': False, 'reason': 'stale_action',
    }
    assert apply_skill_purchase(1, current['token'])['success'] is True

    attributes = {
        key: int(get_player(1)[key])
        for key in ('strength', 'agility', 'intuition', 'vitality', 'wisdom', 'luck')
    }
    travel_preview = attribute_redistribution_preview(1, attributes)
    conn = get_connection()
    conn.execute(
        "UPDATE players SET location_id='westwild_n1',travel_revision=travel_revision+1 WHERE telegram_id=1",
    )
    conn.commit()
    conn.close()
    assert apply_attribute_redistribution(1, travel_preview['token']) == {
        'success': False, 'reason': 'stale_action',
    }

    conn = get_connection()
    conn.execute(
        "UPDATE players SET location_id='capital_city',travel_revision=travel_revision+1 WHERE telegram_id=1",
    )
    conn.commit()
    conn.close()
    reset = issue_family_reset_intent(1, 'bow')
    points_before = _rows(
        "SELECT skill_points FROM weapon_mastery WHERE telegram_id=1 AND weapon_id='bow'",
    )[0]['skill_points']
    conn = get_connection()
    conn.execute('UPDATE players SET in_battle=1 WHERE telegram_id=1')
    conn.commit()
    conn.close()
    assert apply_family_reset(1, reset['token']) == {
        'success': False, 'reason': 'in_battle',
    }
    assert _rows(
        "SELECT skill_points FROM weapon_mastery WHERE telegram_id=1 AND weapon_id='bow'",
    )[0]['skill_points'] == points_before
    assert _rows(
        "SELECT level FROM player_skills WHERE telegram_id=1 AND skill_id='quick_shot'",
    ) == [{'level': 1}]

