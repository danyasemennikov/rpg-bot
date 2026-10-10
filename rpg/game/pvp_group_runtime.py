"""Durable multiple-actor resolution and individual consequences for PvP PXE1."""

from fractions import Fraction
import hashlib
import json

from game.action_receipts import ActionRejected
from game.combat_identity import advance_affected_side, combat_seed, evaluate_action
from game.combat_orders import load_combat_orders, persist_turn_result, submit_combat_order
from game.location_threats import arrive_at_location
from game.pvp_death_policy import resolve_death_respawn_hub, resolve_pvp_death_loss_percent
from game.pvp_inventory_policy import resolve_item_death_vulnerability
from game.pvp_rules import resolve_kill_infamy_delta
from game.pvp_world import encoded, engagement, iso, milliseconds, player


def locked_sides(row):
    try:
        roster = json.loads(row['locked_roster_json'])
        if any(not isinstance(m['player_id'],int) or isinstance(m['player_id'],bool)
               for side in ('side_a','side_b') for m in roster[side]):
            raise ValueError()
        sides = {side: [int(m['player_id']) for m in roster[side]] for side in ('side_a','side_b')}
        if roster['schema_version'] != 1 or any(not 1 <= len(ids) <= 2 for ids in sides.values()):
            raise ValueError()
        if sides['side_a'][0] != row['attacker_id'] or sides['side_b'][0] != row['defender_id']:
            raise ValueError()
        if len(set(sides['side_a']+sides['side_b'])) != len(sides['side_a']+sides['side_b']):
            raise ValueError()
        return sides
    except (TypeError,ValueError,KeyError,IndexError):
        raise ActionRejected('corrupt_roster')


def validate_live_group(conn,row):
    """Validate persisted identities and timing without rebuilding snapshots."""
    try:
        sides = locked_sides(row)
        context = json.loads(row['reason_context'])
        battle = context['battle']
        ids = sides['side_a']+sides['side_b']
        if (not isinstance(row['roster_locked_ms'],int) or row['roster_locked_ms']<0
                or not isinstance(context,dict) or not isinstance(battle,dict)
                or battle['state']!='live' or battle['rules_version']!=row['rules_version']
                or battle['world_model_version']!=1 or battle['combat_seed']!=row['combat_seed']
                or len(row['combat_seed'])!=32 or any(c not in '0123456789abcdef' for c in row['combat_seed'])
                or battle['active_side'] not in sides or battle['turn_revision'] not in {row['turn_revision'],row['turn_revision']+1}
                or not isinstance(battle['participants_v1'],dict)
                or set(battle['participants_v1'])!={str(p) for p in ids}
                or not isinstance(battle['manual_actor_ids'],list)
                or not set(battle['manual_actor_ids'])<=set(ids)
                or not isinstance(battle['damage_by_source'],dict)):
            raise ValueError()
        milliseconds(battle['side_deadline_at'])
        for actor_id in ids:
            actor = battle['participants_v1'][str(actor_id)]
            if (not isinstance(actor,dict) or actor['actor_id']!=actor_id
                    or actor['rules_version']!=row['rules_version']
                    or not isinstance(actor['effects'],list) or not isinstance(actor['cooldowns'],dict)
                    or any(not isinstance(actor[key],int) or isinstance(actor[key],bool)
                           for key in ('hp','max_hp','mana','max_mana'))
                    or not 0<=actor['hp']<=actor['max_hp'] or not 0<=actor['mana']<=actor['max_mana']):
                raise ValueError()
        roster = json.loads(row['locked_roster_json'])
        locked_allies = {r['ally_id'] for r in conn.execute("SELECT ally_id FROM pvp_engagement_reinforcements WHERE engagement_id=? AND membership_version=1 AND status IN ('locked','settled')",(row['id'],))}
        if locked_allies!=set(sides['side_a'][1:]+sides['side_b'][1:]):
            raise ValueError()
        for side,principal,member_side in (('side_a',row['attacker_id'],'initiator'),('side_b',row['defender_id'],'defender')):
            for member in roster[side][1:]:
                membership = conn.execute("""SELECT status FROM pvp_engagement_reinforcements WHERE id=?
                    AND engagement_id=? AND ally_id=? AND inviter_id=? AND side=?
                    AND membership_version=1 AND status IN ('locked','settled')""",
                    (member['reinforcement_id'],row['id'],member['player_id'],principal,member_side)).fetchone()
                if not membership:
                    raise ValueError()
                if membership['status']=='settled':
                    receipt=conn.execute('''SELECT result_json FROM pvp_participant_settlements_pxe1
                        WHERE engagement_id=? AND player_id=? AND status='applied' ''',
                        (row['id'],member['player_id'])).fetchone()
                    proof=json.loads(receipt['result_json']) if receipt else {}
                    if (battle['participants_v1'][str(member['player_id'])]['hp']!=0
                            or proof.get('engagement_id')!=row['id']
                            or proof.get('player_id')!=member['player_id']):
                        raise ValueError()
        return context
    except (ActionRejected,ValueError,TypeError,KeyError,IndexError,AttributeError):
        raise ActionRejected('corrupt_live_state')


def quarantine_live_group(conn,row,*,reason,now_ms):
    """Interrupt this engagement; immutable losses and orders remain evidence."""
    if not conn.in_transaction:
        raise RuntimeError('PvP quarantine requires a caller-owned writer')
    if row['world_model_version']!=1 or row['engagement_state']!='converted_to_battle':
        return
    recipients = {row['attacker_id'],row['defender_id']}
    recipients.update(r['ally_id'] for r in conn.execute("""SELECT ally_id FROM pvp_engagement_reinforcements
        WHERE engagement_id=? AND membership_version=1 AND status IN ('accepted','locked')""",(row['id'],)))
    context = {'quarantined_reason_context':row['reason_context'],'terminal_reason':reason}
    conn.execute("UPDATE pvp_engagements SET engagement_state='cancelled',reason_context=?,state_revision=state_revision+1 WHERE id=?",
                 (encoded(context),row['id']))
    conn.execute("""UPDATE pvp_engagement_reinforcements SET status='expired',responded_at=?
        WHERE engagement_id=? AND membership_version=1 AND status IN ('accepted','locked','pending')""",(iso(now_ms),row['id']))
    from game.player_experience_schema import _recovery_notice
    for actor_id in recipients:
        other_pve = conn.execute("""SELECT 1 FROM pve_encounter_participants p JOIN pve_encounters e
            ON e.encounter_id=p.encounter_id WHERE p.player_id=? AND p.status='active'
            AND e.status IN ('active','forming','resolving_victory')""",(actor_id,)).fetchone()
        other_pvp = conn.execute("""SELECT 1 FROM pvp_engagements e WHERE e.id<>?
            AND e.engagement_state IN ('pending','active','converted_to_battle') AND
            (e.attacker_id=? OR e.defender_id=? OR EXISTS(SELECT 1 FROM pvp_engagement_reinforcements r
                WHERE r.engagement_id=e.id AND r.ally_id=? AND r.status IN ('accepted','locked')))""",
            (row['id'],actor_id,actor_id,actor_id)).fetchone()
        if not other_pve and not other_pvp:
            conn.execute('UPDATE players SET in_battle=0 WHERE telegram_id=?',(actor_id,))
        _recovery_notice(conn,actor_id,domain='pvp',ref=row['id'],reason='cancelled',now_ms=now_ms)
    import logging
    logging.getLogger(__name__).error('PXE1 quarantined live PvP engagement %s: %s',row['id'],reason)


def living(battle, ids):
    return [p for p in ids if int(battle['participants_v1'][str(p)]['hp']) > 0
            and not battle['participants_v1'][str(p)].get('dead')]


def authorize_order(conn, row, battle, actor_id, action, *, deadline_at=None):
    sides = locked_sides(row)
    active = battle['active_side']
    opposite = 'side_b' if active == 'side_a' else 'side_a'
    if row['engagement_state'] != 'converted_to_battle' or battle['state'] != 'live':
        raise ActionRejected('not_live')
    if actor_id not in living(battle, sides[active]):
        raise ActionRejected('not_your_turn')
    if actor_id not in (row['attacker_id'],row['defender_id']):
        if not conn.execute("SELECT 1 FROM pvp_engagement_reinforcements WHERE engagement_id=? AND ally_id=? AND membership_version=1 AND status='locked'", (row['id'],actor_id)).fetchone():
            raise ActionRejected('not_participant')
    if conn.execute('SELECT 1 FROM pvp_participant_settlements_pxe1 WHERE engagement_id=? AND player_id=?', (row['id'],actor_id)).fetchone():
        raise ActionRejected('dead')
    if deadline_at is not None and deadline_at != battle['side_deadline_at']:
        raise ActionRejected('stale_action')
    from game.pvp_live import _v1_action_ready
    kind = action.get('kind')
    action_id = 'normal_attack' if kind == 'normal' else f"skill:{action.get('skill_id')}" if kind == 'skill' else 'guard'
    if kind not in {'normal','guard','timeout_guard','skill'} or not _v1_action_ready(battle['participants_v1'][str(actor_id)],action_id):
        raise ActionRejected('invalid_action')
    target = action.get('target_id')
    if kind in {'normal','skill'} and target not in living(battle,sides[opposite]):
        raise ActionRejected('invalid_target')
    if kind in {'guard','timeout_guard'} and target != actor_id:
        raise ActionRejected('invalid_target')


def record_damage(battle, events, sides):
    actor_side = {str(p):side for side,ids in sides.items() for p in ids}
    for event in events:
        damage = int(event.get('hp_removed',0))
        if damage <= 0:
            continue
        source = str(event.get('source_id') if event.get('kind')=='dot' else event.get('actor_id'))
        victim = str(event.get('target_id'))
        if source not in actor_side or victim not in actor_side or actor_side[source] == actor_side[victim]:
            raise ActionRejected('invalid_damage_provenance')
        by_source = battle.setdefault('damage_by_source',{}).setdefault(victim,{})
        by_source[source] = int(by_source.get(source,0))+damage


def _debit(conn, victim_id, item_id, quantity):
    remaining = quantity
    for stack in conn.execute('SELECT id,quantity FROM inventory WHERE telegram_id=? AND item_id=? AND quantity>0 ORDER BY id', (victim_id,item_id)).fetchall():
        taken = min(remaining,stack['quantity'])
        conn.execute('UPDATE inventory SET quantity=quantity-? WHERE id=?', (taken,stack['id']))
        remaining -= taken
        if not remaining:
            break
    if remaining:
        raise RuntimeError('pvp_pool_debit_mismatch')
    conn.execute('DELETE FROM inventory WHERE telegram_id=? AND quantity<=0', (victim_id,))


def _credit(conn, recipient_id, item_id, quantity):
    if not quantity:
        return
    stack = conn.execute('SELECT id FROM inventory WHERE telegram_id=? AND item_id=? ORDER BY id LIMIT 1', (recipient_id,item_id)).fetchone()
    if stack:
        conn.execute('UPDATE inventory SET quantity=quantity+? WHERE id=?', (quantity,stack['id']))
    else:
        conn.execute('INSERT INTO inventory(telegram_id,item_id,quantity) VALUES (?,?,?)', (recipient_id,item_id,quantity))


def _log_pair(conn, sides, credited_id, victim_id):
    a,b = (credited_id,victim_id) if credited_id in sides['side_a'] else (victim_id,credited_id)
    return conn.execute('''INSERT INTO pvp_log(attacker_id,defender_id,winner_id,exp_gained,gold_gained)
        VALUES (?,?,?,0,0)''', (a,b,credited_id)).lastrowid


def _prior_pair_count(conn, row, opponent_id, victim_id):
    # Exclude this encounter's individual log rows from the historical count.
    own_logs = [json.loads(r['result_json'])['log_id'] for r in conn.execute(
        'SELECT result_json FROM pvp_participant_settlements_pxe1 WHERE engagement_id=?', (row['id'],))]
    placeholders = ','.join('?' for _ in own_logs) or 'NULL'
    return conn.execute(f'''SELECT COUNT(*) FROM pvp_log WHERE winner_id=?
        AND ((attacker_id=? AND defender_id=?) OR (attacker_id=? AND defender_id=?))
        AND fought_at>=datetime('now','-30 minutes') AND (id NOT IN ({placeholders}) OR ?=0)''',
        (opponent_id,opponent_id,victim_id,victim_id,opponent_id,*own_logs,len(own_logs))).fetchone()[0]


def settle_deaths(conn, row, context, *, turn_revision, now_ms, failure_hook=None):
    battle = context['battle']
    sides = locked_sides(row)
    new_deaths = []
    # Freeze every newly defeated victim's prior counts before emitting any log.
    candidates = []
    for side,ids in sides.items():
        opposite = sides['side_b' if side=='side_a' else 'side_a']
        for victim_id in ids:
            if victim_id in living(battle,ids) or conn.execute('SELECT 1 FROM pvp_participant_settlements_pxe1 WHERE engagement_id=? AND player_id=?', (row['id'],victim_id)).fetchone():
                continue
            counts = {str(p):_prior_pair_count(conn,row,p,victim_id) for p in opposite}
            damage = battle.get('damage_by_source',{}).get(str(victim_id),{})
            if any(str(p) not in {str(o) for o in opposite} or int(n)<0 for p,n in damage.items()):
                raise ActionRejected('invalid_damage_provenance')
            credited = max(opposite,key=lambda p:(int(damage.get(str(p),0)),-opposite.index(p)))
            candidates.append((side,victim_id,credited,counts))
    for side,victim_id,credited,counts in candidates:
        victim = player(conn,victim_id)
        snapshot = battle['participants_v1'][str(victim_id)]
        maximum = max(counts.values(),default=0)
        scale = Fraction(1) if maximum==0 else Fraction(1,2) if maximum==1 else Fraction(1,4)
        loss = Fraction(str(resolve_pvp_death_loss_percent(location_id=row['location_id'])))*scale
        pool = {}
        quantities = {}
        for item in conn.execute('SELECT item_id,SUM(quantity) AS quantity FROM inventory WHERE telegram_id=? AND quantity>0 GROUP BY item_id', (victim_id,)).fetchall():
            if not resolve_item_death_vulnerability(item['item_id']).vulnerable_on_pvp_death:
                continue
            quantity = int(item['quantity'])
            quantities[item['item_id']] = quantity
            removed = quantity*loss.numerator//loss.denominator
            if removed:
                _debit(conn,victim_id,item['item_id'],removed)
                pool[item['item_id']] = removed
        crime = context.get('crime_context',{}).get(str(credited))
        infamy = 0
        if credited in sides['side_a']:
            if not crime:
                raise ActionRejected('missing_crime_provenance')
            infamy = resolve_kill_infamy_delta(winner=crime['initiator_snapshot'],loser=victim,
                initiator=crime['initiator_snapshot'],initial_target=crime['original_defender_snapshot'],
                location_id=row['location_id'],repeat_kill_count=counts[str(credited)],
                conn=conn,retaliation_context=crime['retaliation_context'])
        log_id = _log_pair(conn,sides,credited,victim_id)
        if infamy:
            conn.execute('UPDATE players SET infamy=infamy+?,red_flag=1 WHERE telegram_id=?',(infamy,credited))
        hub = resolve_death_respawn_hub(location_id=row['location_id'])
        arrive_at_location(conn,victim_id,hub,now_ms=now_ms)
        conn.execute('''UPDATE players SET hp=?,mana=?,in_battle=0,pvp_respawn_protection_until=?
            WHERE telegram_id=?''', (max(1,int(victim['max_hp'])*30//100),max(0,int(snapshot['mana'])),now_ms//1000+480,victim_id))
        result = {'schema_version':1,'engagement_id':row['id'],'player_id':victim_id,'side':side,
            'credited_actor_id':credited,'prior_pair_counts':counts,'repeat_scale':float(scale),
            'inventory_before':quantities,'loss_pool':pool,'log_id':log_id,'infamy_delta':infamy,
            'respawn_hub':hub,'hp_after':max(1,int(victim['max_hp'])*30//100),'mana_after':max(0,int(snapshot['mana']))}
        result['damage_dealt']=sum(int(sources.get(str(victim_id),0)) for sources in battle.get('damage_by_source',{}).values())
        result['damage_taken']=sum(int(n) for n in battle.get('damage_by_source',{}).get(str(victim_id),{}).values())
        new_deaths.append(result)
    # Finalize each new receipt once, after every death consequence in this
    # atomic batch. Simultaneous DOT deaths can change the credited actor's
    # infamy even when that actor was already processed earlier in the batch.
    prior_deaths=[json.loads(r[0]) for r in conn.execute('SELECT result_json FROM pvp_participant_settlements_pxe1 WHERE engagement_id=?',(row['id'],))]
    for result in new_deaths:
        victim_id=result['player_id']
        result['personal_infamy_delta']=int(context.get('crime_context',{}).get(str(victim_id),{}).get('initiation_infamy',0))
        result['personal_infamy_delta']+=sum(d['infamy_delta'] for d in prior_deaths+new_deaths if d['credited_actor_id']==victim_id)
        conn.execute('''INSERT INTO pvp_participant_settlements_pxe1
            (engagement_id,player_id,schema_version,turn_revision,result_json,status,created_ms)
            VALUES (?,?,1,?,?,'applied',?)''',(row['id'],victim_id,turn_revision,encoded(result),now_ms))
        from game.player_feedback import record_combat_result
        record_combat_result(conn,victim_id,domain='pvp',ref=row['id'],phase='death',now_ms=now_ms)
        conn.execute("""UPDATE pvp_engagement_reinforcements SET status='settled'
            WHERE engagement_id=? AND ally_id=? AND membership_version=1 AND status='locked'""",
            (row['id'],victim_id))
        if failure_hook:
            failure_hook('after_participant_receipt')
    return new_deaths


def settle_group(conn, row, context, *, turn_revision, now_ms, failure_hook=None):
    prior = conn.execute('SELECT result_json FROM pvp_group_settlements_pxe1 WHERE engagement_id=?', (row['id'],)).fetchone()
    if prior:
        return json.loads(prior['result_json'])
    battle = context['battle']
    sides = locked_sides(row)
    alive = {side:living(battle,ids) for side,ids in sides.items()}
    if all(alive.values()):
        return None
    winner = 'side_a' if alive['side_a'] else 'side_b' if alive['side_b'] else None
    eligible = [p for p in alive.get(winner,[]) if p in battle.get('manual_actor_ids',[])]
    grants, destroyed, relationships = [],[],[]
    for death in conn.execute('SELECT result_json FROM pvp_participant_settlements_pxe1 WHERE engagement_id=? ORDER BY player_id', (row['id'],)).fetchall():
        receipt = json.loads(death['result_json'])
        victim_id = receipt['player_id']
        recipients = eligible if winner and receipt['side'] != winner else []
        for item_id,quantity in receipt['loss_pool'].items():
            if not recipients:
                destroyed.append({'victim_id':victim_id,'item_id':item_id,'quantity':quantity})
                continue
            ordered = sorted(recipients,key=lambda p:hashlib.sha256(encoded([row['combat_seed'],victim_id,item_id,p]).encode('utf-8')).hexdigest())
            base,remainder = divmod(quantity,len(ordered))
            for index,recipient_id in enumerate(ordered):
                amount = base+int(index<remainder)
                _credit(conn,recipient_id,item_id,amount)
                grants.append({'victim_id':victim_id,'item_id':item_id,'recipient_id':recipient_id,'quantity':amount})
        for recipient_id in recipients:
            if recipient_id != receipt['credited_actor_id']:
                relationships.append({'victim_id':victim_id,'recipient_id':recipient_id,'log_id':_log_pair(conn,sides,recipient_id,victim_id)})
    for side,ids in alive.items():
        for player_id in ids:
            actor = battle['participants_v1'][str(player_id)]
            conn.execute('UPDATE players SET hp=?,mana=?,in_battle=0 WHERE telegram_id=?',(actor['hp'],actor['mana'],player_id))
    battle['state'] = 'finished'
    battle['winner_side'] = winner
    battle['side_turn_state'] = 'completed'
    battle['side_deadline_at'] = None
    result = {'schema_version':1,'engagement_id':row['id'],'winner_side':winner,
              'eligible_recipients':eligible,'grants':grants,'destroyed':destroyed,'relationships':relationships}
    conn.execute('''INSERT INTO pvp_group_settlements_pxe1
        (engagement_id,schema_version,terminal_turn_revision,result_json,status,created_ms)
        VALUES (?,1,?,?,'applied',?)''',(row['id'],turn_revision,encoded(result),now_ms))
    conn.execute("UPDATE pvp_engagements SET engagement_state='cancelled' WHERE id=?",(row['id'],))
    conn.execute("""UPDATE pvp_engagement_reinforcements SET status='settled'
        WHERE engagement_id=? AND membership_version=1 AND status IN ('accepted','locked')""",(row['id'],))
    from game.player_feedback import record_combat_result
    for ids in alive.values():
        for player_id in ids:
            record_combat_result(conn,player_id,domain='pvp',ref=row['id'],phase='terminal',now_ms=now_ms)
    if failure_hook:
        failure_hook('after_group_receipt')
    return result


def resolve_group_turn(conn, *, engagement_id, actor_id=None, action=None, now_ms, failure_hook=None):
    if not conn.in_transaction:
        raise RuntimeError('PvP resolution requires a caller-owned writer')
    row = engagement(conn,engagement_id)
    context = json.loads(row['reason_context'])
    battle = context.get('battle') or {}
    if battle.get('state') != 'live':
        return 'not_live',context
    context = validate_live_group(conn,row)
    battle = context['battle']
    sides = locked_sides(row)
    active = battle['active_side']
    opposite = 'side_b' if active=='side_a' else 'side_a'
    revision = int(battle['turn_revision'])
    deadline = battle['side_deadline_at']
    active_ids = living(battle,sides[active])
    if action is not None:
        prior_order = conn.execute('''SELECT action_json FROM combat_orders_v1 WHERE encounter_kind='pvp'
            AND encounter_id=? AND turn_revision=? AND actor_id=?''',(str(engagement_id),revision,actor_id)).fetchone()
        if now_ms >= milliseconds(deadline) and not (prior_order and json.loads(prior_order['action_json'])==action):
            raise ActionRejected('deadline_elapsed')
        authorize_order(conn,row,battle,actor_id,action)
        submitted = submit_combat_order(encounter_kind='pvp',encounter_id=str(engagement_id),turn_revision=revision,
            actor_id=actor_id,action=action,target_id=action.get('target_id'),deadline_at=deadline,conn=conn)
        if not submitted['accepted']:
            raise ActionRejected(submitted['reason'])
    orders = {o['actor_id']:o for o in load_combat_orders(encounter_kind='pvp',encounter_id=str(engagement_id),turn_revision=revision,conn=conn)}
    if now_ms >= milliseconds(deadline):
        for missing in active_ids:
            if missing in orders:
                continue
            fallback = {'kind':'timeout_guard','target_id':missing,'manual':False}
            submit_combat_order(encounter_kind='pvp',encounter_id=str(engagement_id),turn_revision=revision,
                actor_id=missing,action=fallback,target_id=missing,deadline_at=deadline,order_kind='timeout',conn=conn)
        orders = {o['actor_id']:o for o in load_combat_orders(encounter_kind='pvp',encounter_id=str(engagement_id),turn_revision=revision,conn=conn)}
    if not all(p in orders for p in active_ids):
        return 'waiting',context
    actors = battle['participants_v1']
    events = []
    for player_id in active_ids:
        if player_id not in living(battle,active_ids):
            continue
        order = orders[player_id]
        selected = dict(order['action'])
        manual = order['order_kind']=='manual'
        from game.pvp_live import _v1_action_ready
        kind = selected.get('kind')
        action_id = 'normal_attack' if kind=='normal' else 'guard' if kind in {'guard','timeout_guard'} else 'skill:'+str(selected.get('skill_id'))
        if kind not in {'normal','guard','timeout_guard','skill'} or not _v1_action_ready(actors[str(player_id)],action_id):
            raise ActionRejected('invalid_durable_order')
        if ((kind in {'normal','skill'} and selected.get('target_id') not in sides[opposite])
                or (kind in {'guard','timeout_guard'} and selected.get('target_id')!=player_id)):
            raise ActionRejected('invalid_durable_order')
        selected['manual'] = manual
        if manual and player_id not in battle['manual_actor_ids']:
            battle['manual_actor_ids'].append(player_id)
        if selected['kind'] in {'normal','skill'} and selected.get('target_id') not in living(battle,sides[opposite]):
            events.append({'kind':'target_dead_guard','actor_id':player_id,'target_id':selected.get('target_id')})
            selected = {'kind':'guard','target_id':player_id,'manual':manual}
        result = evaluate_action(actors[str(player_id)], [actors[str(p)] for p in sides[active]],
            [actors[str(p)] for p in sides[opposite]], selected,
            rng_seed=combat_seed(row['combat_seed'],revision,player_id,selected.get('target_id'),sides[active].index(player_id)),side_index=revision)
        if not result['accepted']:
            raise ActionRejected('invalid_durable_order')
        for entity in result['allies']+result['opponents']:
            actors[str(entity['actor_id'])] = entity
        events.extend(result['events'])
    tick = advance_affected_side([actors[str(p)] for p in sides[active]],side_index=revision)
    for entity in tick['entities']:
        actors[str(entity['actor_id'])] = entity
    events.extend(tick['events'])
    record_damage(battle,events,sides)
    battle.setdefault('events_v1',[]).extend(events)
    deaths = settle_deaths(conn,row,context,turn_revision=revision,now_ms=now_ms,failure_hook=failure_hook)
    terminal = settle_group(conn,row,context,turn_revision=revision,now_ms=now_ms,failure_hook=failure_hook)
    if terminal is None:
        battle.update(active_side=opposite,turn_revision=revision+1,side_deadline_at=iso(now_ms+15000))
    context['state_revision'] = row['state_revision']
    result = persist_turn_result(encounter_kind='pvp',encounter_id=str(engagement_id),turn_revision=revision,
        result={'events':events,'deaths':deaths,'group_settlement':terminal},complete_state=context,
        expected_previous_revision=row['turn_revision'],conn=conn)
    if not result['applied'] or result.get('duplicate'):
        raise RuntimeError('pvp_side_result_conflict')
    if failure_hook:
        failure_hook('after_side_result')
    return 'finished' if terminal is not None else 'resolved',context
