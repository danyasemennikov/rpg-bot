"""One effective item requirement policy; only permanent player stats qualify."""
from game.action_receipts import ActionRejected

POLICY_VERSION=1
STATS=('strength','agility','intuition','wisdom')
WEAPON_PRIMARY={'sword_1h':'strength','sword_2h':'strength','axe_2h':'strength',
    'daggers':'agility','bow':'agility','magic_staff':'intuition','wand':'intuition',
    'holy_staff':'wisdom','holy_rod':'wisdom','tome':'wisdom'}
OFFHAND_PRIMARY={'shield':'strength','focus':'intuition','censer':'wisdom'}
ARMOR_PRIMARY={'heavy':'strength','medium':'agility','light':'wisdom'}


def resolve_effective_equip_requirements(base_template,instance_tier=None,*,family=None,policy_version=POLICY_VERSION):
    if policy_version!=POLICY_VERSION:
        raise ActionRejected('unsupported_equipment_policy')
    item=dict(base_template or {})
    requirements={'req_level':max(1,int(item.get('req_level',1) or 1)),
                  **{'req_'+stat:max(0,int(item.get('req_'+stat,0) or 0)) for stat in STATS},
                  'policy_version':POLICY_VERSION}
    if instance_tier is None:
        return requirements
    if type(instance_tier) is not int or instance_tier<=0:
        raise ActionRejected('unsupported_equipment_policy')
    requirements['req_level']=max(requirements['req_level'],instance_tier)
    from game.itemization import get_item_archetype_metadata
    metadata=get_item_archetype_metadata(item)
    weapon=family or metadata.get('weapon_profile')
    offhand=metadata.get('offhand_profile')
    armor=metadata.get('armor_class')
    primary=WEAPON_PRIMARY.get(weapon)
    weapon_policy=primary is not None
    if primary is None:
        primary=OFFHAND_PRIMARY.get(offhand) or ARMOR_PRIMARY.get(armor)
    accessory=metadata.get('slot_identity') in ('ring','amulet')
    field=bool(item.get('field_catalog_version'))
    if instance_tier>20 and (primary or field) or field and not primary and not accessory:
        raise ActionRejected('unsupported_equipment_policy')
    if primary:
        band=max(t for t in (1,5,10,15,20) if t<=instance_tier)
        minimum=({1:1,5:4,10:7,15:10,20:13} if weapon_policy else {1:1,5:3,10:5,15:7,20:9})[band]
        requirements['req_'+primary]=max(requirements['req_'+primary],minimum)
    return requirements


def meets_requirements(player,requirements):
    player=dict(player)
    return all(int(player.get(stat,0) or 0)>=requirements['req_'+stat] for stat in ('level',)+STATS)


def require_equip(player,template,instance_tier=None):
    requirements=resolve_effective_equip_requirements(template,instance_tier)
    if not meets_requirements(player,requirements):
        raise ActionRejected('equipment_requirements')
    return requirements


def normalize_equipment(conn,player_id):
    """Revalidate saved gear before use; tier/stat writes call this in their writer."""
    owns_transaction=not conn.in_transaction
    if owns_transaction:
        conn.execute('BEGIN IMMEDIATE')
    try:
        from game.items_data import get_item
        player=conn.execute('SELECT * FROM players WHERE telegram_id=?',(player_id,)).fetchone()
        if not player:
            if owns_transaction:
                conn.rollback()
            return []
        removed=[]
        for row in conn.execute('SELECT * FROM gear_instances WHERE telegram_id=? AND equipped_slot IS NOT NULL',(player_id,)).fetchall():
            try:
                require_equip(player,get_item(row['base_item_id']),row['item_tier'])
                valid=True
            except ActionRejected:
                valid=False
            if not valid:
                conn.execute('UPDATE gear_instances SET equipped_slot=NULL,revision=revision+1 WHERE id=?',(row['id'],))
                removed.append({'source':'instance','instance_id':row['id'],'slot':row['equipped_slot']})
        equipment=conn.execute('SELECT * FROM equipment WHERE telegram_id=?',(player_id,)).fetchone()
        if equipment:
            from game.gear_instances import LEGACY_EQUIPMENT_SLOT_KEYS
            for slot in LEGACY_EQUIPMENT_SLOT_KEYS:
                if equipment[slot] is None:
                    continue
                inventory=conn.execute('SELECT item_id FROM inventory WHERE id=? AND telegram_id=?',(equipment[slot],player_id)).fetchone()
                try:
                    if not inventory:
                        raise ActionRejected('gear_not_owned')
                    require_equip(player,get_item(inventory['item_id']))
                    valid=True
                except ActionRejected:
                    valid=False
                if not valid:
                    conn.execute(f'UPDATE equipment SET {slot}=NULL WHERE telegram_id=?',(player_id,))
                    removed.append({'source':'legacy','inventory_id':equipment[slot],'slot':slot})
        if removed:
            conn.execute('UPDATE players SET gear_revision=gear_revision+1 WHERE telegram_id=?',(player_id,))
            from game.equipment_stats import aggregate_equipped_stat_bonuses,build_effective_player_stats
            caps=build_effective_player_stats(dict(player),aggregate_equipped_stat_bonuses(player_id,conn=conn))
            conn.execute('UPDATE players SET hp=MIN(hp,?),mana=MIN(mana,?) WHERE telegram_id=?',
                         (caps['max_hp'],caps['max_mana'],player_id))
        if owns_transaction:
            conn.commit()
        return removed
    except Exception:
        if owns_transaction:
            conn.rollback()
        raise
