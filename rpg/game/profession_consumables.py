"""Frozen V2.2 consumables: pending slots and encounter-owned runtime effects."""
from __future__ import annotations

import copy
import json

from game.action_receipts import ActionRejected

# Percentages apply to ratings/capacities, never directly to hit or mitigation.
CONSUMABLES = {
    'a25_resin_salve': {'restore_hp':25},
    'a25_antivenom': {'slot':'preparation','poison_charges':2},
    'a25_clear_sight': {'slot':'preparation','accuracy':8,'accuracy_opportunities':3},
    'a25_mana_infusion': {'slot':'preparation','max_mana':12},
    'a25_cleanse_draught': {'cleanse':True},
    'a25_balanced_elixir': {'slot':'preparation','max_hp':8,'max_mana':8},
    'a25_mushroom_soup': {'restore_hp':15,'restore_mana':15},
    'a25_dry_ration': {'slot':'food','max_hp':6},
    'a25_hunters_stew': {'slot':'food','accuracy':6,'max_hp':4},
    'a25_oil_fish_broth': {'slot':'food','max_mana':8},
    'a25_long_trail_meal': {'restore_hp':30,'restore_mana':20},
    'a25_deepwater_supper': {'slot':'food','physical_defense':6,'magic_defense':6},
}


def pending_slot(conn, player_id, slot):
    row=conn.execute('SELECT * FROM player_consumable_slots WHERE player_id=? AND slot=?',
                     (player_id,slot)).fetchone()
    return dict(row) if row else {'item_id':None,'revision':0}


def use_payload(conn, player_id, inventory_id, quantity, *, confirmed=False):
    row=conn.execute('SELECT item_id FROM inventory WHERE id=? AND telegram_id=?',
                     (inventory_id,player_id)).fetchone()
    spec=CONSUMABLES.get(row['item_id'] if row else '',{})
    if not spec:
        return f'{inventory_id}:{quantity}'
    slot=pending_slot(conn,player_id,spec['slot']) if 'slot' in spec else {'revision':0,'item_id':None}
    return json.dumps({'inventory_id':inventory_id,'quantity':quantity,'slot_revision':slot['revision'],
                       'confirmed':bool(confirmed)},sort_keys=True,separators=(',',':'))


def debit_item(conn, row):
    if row['quantity']==1:
        conn.execute('DELETE FROM inventory WHERE id=?',(row['id'],))
    else:
        conn.execute('UPDATE inventory SET quantity=quantity-1 WHERE id=?',(row['id'],))


def consume(conn, player_id, row, *, hp, mana, max_hp, max_mana,
            expected_revision=None, confirmed=False, in_battle=False):
    spec=CONSUMABLES[row['item_id']]
    if in_battle or spec.get('cleanse'):
        raise ActionRejected('consumable_wrong_context')
    if 'slot' in spec:
        slot=pending_slot(conn,player_id,spec['slot'])
        if expected_revision is None or slot['revision']!=expected_revision:
            raise ActionRejected('stale_action')
        if slot['item_id'] and not confirmed:
            raise ActionRejected('consumable_replace_required')
        conn.execute('''INSERT INTO player_consumable_slots(player_id,slot,item_id,revision)
            VALUES (?,?,?,1) ON CONFLICT(player_id,slot) DO UPDATE SET
            item_id=excluded.item_id,revision=player_consumable_slots.revision+1''',
            (player_id,spec['slot'],row['item_id']))
    heal=min(max(0,max_hp-hp),max_hp*spec.get('restore_hp',0)//100)
    mana_gain=min(max(0,max_mana-mana),max_mana*spec.get('restore_mana',0)//100)
    conn.execute('UPDATE players SET hp=?,mana=? WHERE telegram_id=?',(hp+heal,mana+mana_gain,player_id))
    debit_item(conn,row)
    return {'status':'used','heal':heal,'mana':mana_gain,'item_id':row['item_id'],
            'slot':spec.get('slot')}


def bind_next_battle(conn, player_id, encounter_kind, encounter_id, actor):
    """Call only from the encounter creation/roster-lock writer, never previews.

    The initial binding receipt survives restart/retry. Runtime counters then
    live exclusively in the established persisted actor, not in these slots.
    """
    if not conn.in_transaction:
        raise RuntimeError('Consumable binding requires a caller-owned writer')
    row=conn.execute('''SELECT actor_json FROM consumable_battle_bindings
        WHERE player_id=? AND encounter_kind=? AND encounter_id=?''',
        (player_id,encounter_kind,str(encounter_id))).fetchone()
    if row:
        return json.loads(row['actor_json'])
    actor=copy.deepcopy(actor)
    slots=conn.execute('SELECT * FROM player_consumable_slots WHERE player_id=? AND item_id IS NOT NULL ORDER BY slot',
                        (player_id,)).fetchall()
    effects=[]
    bonuses={}
    for slot in slots:
        spec=CONSUMABLES[slot['item_id']]
        effects.append({'item_id':slot['item_id'],**spec})
        for key in ('max_hp','max_mana','physical_defense','magic_defense'):
            bonuses[key]=bonuses.get(key,0)+spec.get(key,0)
        conn.execute('UPDATE player_consumable_slots SET item_id=NULL,revision=revision+1 WHERE player_id=? AND slot=?',
                      (player_id,slot['slot']))
    actor['profession_consumables']=effects
    actor['consumable_base_caps']={key:int(actor[key]) for key in ('max_hp','max_mana')}
    for key,percent in bonuses.items():
        actor[key]=int(actor[key])+int(actor[key])*percent//100
    # No assignment to hp/mana: capacity is not restoration.
    conn.execute('INSERT INTO consumable_battle_bindings(player_id,encounter_kind,encounter_id,actor_json) VALUES (?,?,?,?)',
                  (player_id,encounter_kind,str(encounter_id),json.dumps(actor,sort_keys=True)))
    return actor


def accuracy_rating(actor):
    percent=sum(e.get('accuracy',0) for e in actor.get('profession_consumables',[])
        if 'accuracy_opportunities' not in e or int(actor.get('opportunity_index',0))<e['accuracy_opportunities'])
    rating=int(actor.get('accuracy',100))
    return rating+rating*percent//100


def shorten_poison(target, effect):
    for preparation in target.get('profession_consumables',[]):
        if preparation.get('poison_charges',0)>0:
            effect['duration']=max(1,int(effect['duration'])-1)
            preparation['poison_charges']-=1
            break


def clamp_after_battle(conn, player_id):
    """Drop encounter-only capacity without free restoration on any exit."""
    from game.equipment_stats import get_player_effective_stats
    row=conn.execute('SELECT * FROM players WHERE telegram_id=?',(player_id,)).fetchone()
    if not row:
        return
    caps=get_player_effective_stats(player_id,dict(row),conn=conn)
    conn.execute('UPDATE players SET hp=MIN(hp,?),mana=MIN(mana,?) WHERE telegram_id=?',
                 (caps['max_hp'],caps['max_mana'],player_id))
