import pytest
import database
from game.items_data import ITEMS
from game.equip_requirements import resolve_effective_equip_requirements,require_equip,WEAPON_PRIMARY
from game.action_receipts import ActionRejected
from game.gear_instances import create_gear_instance,equip_gear_instance_in_slot,set_gear_instance_equipped_slot
from game.gear_progression import issue_gear_intent,apply_gear_intent,build_gear_mutation_preview
from game.tier_advancement import AdvancementRequest,advance_gear_instance_tier,resolve_advancement_cost


@pytest.mark.parametrize('family',WEAPON_PRIMARY)
@pytest.mark.parametrize('tier,minimum',[(1,1),(5,4),(10,7),(15,10),(20,13)])
def test_weapon_requirements_use_actual_tier_and_base_attributes(family,tier,minimum):
    item=ITEMS['field_'+family]
    req=resolve_effective_equip_requirements(item,tier)
    primary=WEAPON_PRIMARY[family]
    assert req['req_level']==tier
    assert req['req_'+primary]==max(minimum,item['req_'+primary])
    player={'level':tier,'strength':100,'agility':100,'intuition':100,'wisdom':100}
    require_equip(player,item,tier)
    player[primary]=req['req_'+primary]-1
    with pytest.raises(ActionRejected,match='equipment_requirements'):
        require_equip(player,item,tier)


def test_all_instance_writers_block_c1_t20_and_allow_qualified_c20():
    conn=database.get_connection();conn.execute('BEGIN IMMEDIATE')
    instance=create_gear_instance(1,'field_sword_1h',item_tier=20,conn=conn)
    conn.commit();conn.close()
    with pytest.raises(ActionRejected,match='equipment_requirements'):
        equip_gear_instance_in_slot(1,instance,'weapon')
    with pytest.raises(ActionRejected,match='equipment_requirements'):
        set_gear_instance_equipped_slot(1,instance,'weapon')
    token=issue_gear_intent(1,'equip',instance,target_slot='weapon')
    assert apply_gear_intent(1,'equip',token)['status']=='equipment_requirements'
    conn=database.get_connection();conn.execute('UPDATE players SET level=20,strength=13 WHERE telegram_id=1');conn.commit();conn.close()
    token=issue_gear_intent(1,'equip',instance,target_slot='weapon')
    assert apply_gear_intent(1,'equip',token)['status']=='equipped'


@pytest.mark.parametrize('writer',('intent','secondary'))
def test_equipped_tier_advancement_atomically_unequips_at_c1(writer):
    conn=database.get_connection();conn.execute('BEGIN IMMEDIATE')
    instance=create_gear_instance(1,'field_sword_1h',item_tier=1,conn=conn)
    equip_gear_instance_in_slot(1,instance,'weapon',conn=conn)
    cost=resolve_advancement_cost(current_tier=1,target_tier=5,rarity='common')
    conn.execute('UPDATE players SET gold=10000 WHERE telegram_id=1')
    conn.execute('INSERT INTO inventory(telegram_id,item_id,quantity) VALUES (1,?,?)',(cost.material_id,cost.material_qty))
    conn.commit();conn.close()
    if writer=='intent':
        preview=build_gear_mutation_preview(1,'advance',instance)
        assert preview['will_unequip'] is True
        token=issue_gear_intent(1,'advance',instance)
        result=apply_gear_intent(1,'advance',token)
        assert result['status']=='advanced' and result['auto_unequipped']
    else:
        assert advance_gear_instance_tier(AdvancementRequest(1,instance)).status=='advanced'
    conn=database.get_connection()
    try:
        assert conn.execute('SELECT item_tier,equipped_slot FROM gear_instances WHERE id=?',(instance,)).fetchone()[:]==(5,None)
        assert conn.execute('SELECT gold FROM players WHERE telegram_id=1').fetchone()[0]==10000-cost.gold
    finally:conn.close()


def test_attribute_reset_uses_prospective_base_and_restart_normalizes_before_snapshot():
    from game.build_progression import attribute_redistribution_preview,apply_attribute_redistribution
    from game.actor_snapshot import build_actor_snapshot
    conn=database.get_connection();conn.execute('BEGIN IMMEDIATE')
    conn.execute('UPDATE players SET level=20,strength=13 WHERE telegram_id=1')
    instance=create_gear_instance(1,'field_sword_1h',item_tier=20,conn=conn)
    equip_gear_instance_in_slot(1,instance,'weapon',conn=conn)
    conn.commit();conn.close()
    allocation={s:1 for s in ('strength','agility','intuition','vitality','wisdom','luck')}
    preview=attribute_redistribution_preview(1,allocation)
    assert preview['success'] and preview['unequips'][0]['instance_id']==instance
    assert apply_attribute_redistribution(1,preview['token'])['success']
    conn=database.get_connection();conn.execute('BEGIN IMMEDIATE')
    assert conn.execute('SELECT equipped_slot FROM gear_instances WHERE id=?',(instance,)).fetchone()[0] is None
    # Deliberately corrupt a persisted slot to model a policy/restart recheck.
    conn.execute("UPDATE gear_instances SET equipped_slot='weapon' WHERE id=?",(instance,));conn.commit();conn.close()
    conn=database.get_connection();conn.execute('BEGIN IMMEDIATE')
    snapshot=build_actor_snapshot(1,conn=conn)
    assert snapshot['weapon_item_id']!='field_sword_1h'
    assert conn.execute('SELECT equipped_slot FROM gear_instances WHERE id=?',(instance,)).fetchone()[0] is None
    conn.rollback();conn.close()


def test_unknown_future_field_policy_fails_closed_and_intermediate_t_uses_lower_band():
    req=resolve_effective_equip_requirements(ITEMS['field_bow'],7)
    assert req['req_level']==7 and req['req_agility']==4
    with pytest.raises(ActionRejected,match='unsupported_equipment_policy'):
        resolve_effective_equip_requirements(ITEMS['field_bow'],25)


@pytest.mark.parametrize('lang',('ru','en','es'))
def test_compact_card_uses_actual_instance_requirements(lang):
    from handlers.inventory_views import item_card
    from handlers.inventory import make_entry_token,STAT_NAMES
    from game.i18n import t
    conn=database.get_connection();conn.execute('BEGIN IMMEDIATE')
    instance=create_gear_instance(1,'field_sword_1h',item_tier=20,conn=conn)
    conn.commit();conn.close()
    text,_=item_card(1,make_entry_token('gear_instance',instance),'gear',lang)
    assert t('common.level',lang)+' 20' in text
    assert STAT_NAMES[lang]['strength']+' 13' in text


@pytest.mark.parametrize('item_id,primary',[(f'field_{armor}_chest',stat) for armor,stat in [('heavy','strength'),('medium','agility'),('light','wisdom')]]+
                         [('field_shield','strength'),('field_focus','intuition'),('field_censer','wisdom')])
@pytest.mark.parametrize('tier,minimum',[(1,1),(5,3),(10,5),(15,7),(20,9)])
def test_armor_and_offhand_use_a_progression_without_dropping_template_minima(item_id,primary,tier,minimum):
    item=ITEMS[item_id]
    req=resolve_effective_equip_requirements(item,tier)
    assert req['req_level']==max(tier,item['req_level'])
    assert req['req_'+primary]==max(minimum,item['req_'+primary])
    player={'level':tier,'strength':30,'agility':30,'intuition':30,'wisdom':30}
    require_equip(player,item,tier)
    player[primary]=req['req_'+primary]-1
    with pytest.raises(ActionRejected,match='equipment_requirements'):require_equip(player,item,tier)


@pytest.mark.parametrize('slot',('ring1','ring2'))
def test_ring_writers_enforce_actual_c_and_equipment_bonus_cannot_bootstrap_attributes(slot):
    from game.equipment_stats import get_player_effective_stats
    conn=database.get_connection();conn.execute('BEGIN IMMEDIATE')
    ring=create_gear_instance(1,'field_precision_ring',item_tier=20,conn=conn)
    dagger=create_gear_instance(1,'field_daggers',item_tier=20,conn=conn)
    conn.commit();conn.close()
    token=issue_gear_intent(1,'equip',ring,target_slot=slot)
    assert apply_gear_intent(1,'equip',token)['status']=='equipment_requirements'
    conn=database.get_connection();conn.execute('UPDATE players SET level=20,agility=12 WHERE telegram_id=1');conn.commit();conn.close()
    token=issue_gear_intent(1,'equip',ring,target_slot=slot)
    assert apply_gear_intent(1,'equip',token)['status']=='equipped'
    assert get_player_effective_stats(1,dict(database.get_player(1)))['agility']>=13
    token=issue_gear_intent(1,'equip',dagger,target_slot='weapon')
    assert apply_gear_intent(1,'equip',token)['status']=='equipment_requirements'


@pytest.mark.parametrize('writer',('legacy_owner','legacy_intent'))
def test_legacy_entry_uses_explicit_template_minima_without_instance_tier(writer):
    from game.gear_instances import equip_legacy_inventory_in_slot
    from game.gear_progression import issue_legacy_gear_intent,apply_legacy_gear_intent
    conn=database.get_connection()
    inv=conn.execute("INSERT INTO inventory(telegram_id,item_id,quantity) VALUES (1,'iron_sword',1)").lastrowid
    conn.execute('UPDATE players SET level=3,strength=4 WHERE telegram_id=1');conn.commit();conn.close()
    if writer=='legacy_owner':
        with pytest.raises(ActionRejected,match='equipment_requirements'):equip_legacy_inventory_in_slot(1,inv,'weapon')
    else:
        token=issue_legacy_gear_intent(1,'equip',inv,target_slot='weapon')
        assert apply_legacy_gear_intent(1,'equip',token)['status']=='equipment_requirements'
    conn=database.get_connection();conn.execute('UPDATE players SET strength=5 WHERE telegram_id=1');conn.commit();conn.close()
    if writer=='legacy_owner':equip_legacy_inventory_in_slot(1,inv,'weapon')
    else:
        token=issue_legacy_gear_intent(1,'equip',inv,target_slot='weapon')
        assert apply_legacy_gear_intent(1,'equip',token)['status']=='equipped'
