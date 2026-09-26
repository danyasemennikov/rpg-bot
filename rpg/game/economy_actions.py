"""Small language-neutral receipt helpers for peaceful economy mutations."""

from __future__ import annotations

import hashlib
import json


def intent_hash(action_kind: str, player_id: int, parameters: dict) -> str:
    canonical = json.dumps({'action_kind': action_kind, 'player_id': int(player_id),
                            'catalog_version': 1, 'parameters': parameters},
                           sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def find_receipt(conn, player_id: int, request_id: str, action_kind: str, request_hash: str) -> dict | None:
    row = conn.execute('''SELECT action_kind, request_hash, result_json FROM economy_action_receipts
        WHERE player_id=? AND request_id=?''', (player_id, request_id)).fetchone()
    if row is None:
        return None
    if row['action_kind'] != action_kind:
        raise ValueError('request_receipt_mismatch')
    if row['request_hash'] != request_hash:
        # Menu refreshes intentionally replace pending intents. A committed UI
        # receipt still owns its unguessable token and must recover even after
        # the corresponding preview row has been removed.
        token = request_id.removeprefix('ui:') if request_id.startswith('ui:') else None
        pending = token and conn.execute('SELECT 1 FROM player_ui_actions WHERE token=?', (token,)).fetchone()
        if not token or pending:
            raise ValueError('request_receipt_mismatch')
    return json.loads(row['result_json'])


def store_receipt(conn, player_id: int, request_id: str, action_kind: str,
                  request_hash: str, result: dict) -> None:
    conn.execute('''INSERT INTO economy_action_receipts
        (player_id, request_id, action_kind, request_hash, schema_version, catalog_version, result_json)
        VALUES (?, ?, ?, ?, 1, 1, ?)''',
        (player_id, request_id, action_kind, request_hash,
         json.dumps(result, ensure_ascii=False, sort_keys=True)))


def store_business_rejection(conn, *, player_id: int, request_id: str,
                             action_kind: str, request_hash: str, status: str,
                             location_id: str | None = None,
                             recipe_id: str | None = None,
                             gold_after: int = 0,
                             source: dict | None = None,
                             details: dict | None = None) -> dict:
    """Commit a consumed, valid intent's language-neutral rejection result."""
    result = {
        'schema_version': 1, 'action_kind': action_kind, 'status': status,
        'player_id': player_id, 'location_id': location_id, 'recipe_id': recipe_id,
        'consumed': [], 'granted': [], 'gold_delta': 0, 'gold_after': int(gold_after),
        'progression': [], 'source': source or {},
        'details': {'reason': status, **(details or {})},
    }
    store_receipt(conn, player_id, request_id, action_kind, request_hash, result)
    return result


def list_receipts(player_id: int, *, page: int = 0, page_size: int = 5) -> list[dict]:
    from database import get_connection
    page = max(0, int(page))
    conn = get_connection()
    try:
        rows = conn.execute('''SELECT request_id, action_kind, result_json, created_at
            FROM economy_action_receipts WHERE player_id=?
            ORDER BY created_at DESC, request_id DESC LIMIT ? OFFSET ?''',
            (player_id, page_size + 1, page * page_size)).fetchall()
        return [{**json.loads(row['result_json']), 'request_id': row['request_id'],
                 'created_at': row['created_at']} for row in rows]
    finally:
        conn.close()


def get_receipt(player_id: int, request_id: str) -> dict | None:
    from database import get_connection
    conn = get_connection()
    try:
        row = conn.execute('''SELECT request_id, action_kind, result_json, created_at
            FROM economy_action_receipts WHERE player_id=? AND request_id=?''',
            (player_id, request_id)).fetchone()
        if not row:
            return None
        return {**json.loads(row['result_json']), 'request_id': row['request_id'],
                'created_at': row['created_at']}
    finally:
        conn.close()


def rest_at_inn(player_id: int, action_token: str) -> dict:
    from database import get_connection
    from game.action_receipts import ActionRejected, consume_action, peaceful_player
    from game.equipment_stats import get_player_effective_stats
    request_id = f'ui:{action_token}'
    request_hash = intent_hash('inn', player_id, {'service': 'rest', 'cost': 12})
    conn = get_connection()
    authorized = False
    try:
        conn.execute('BEGIN IMMEDIATE')
        recovered = find_receipt(conn, player_id, request_id, 'inn', request_hash)
        if recovered is not None:
            conn.commit(); return {**recovered, 'recovered': True}
        consume_action(conn, player_id, 'inn', action_token, payload='rest:12')
        authorized = True
        player = peaceful_player(conn, player_id, service='inn')
        effective = get_player_effective_stats(player_id, player, conn=conn)
        max_hp, max_mana = int(effective['max_hp']), int(effective['max_mana'])
        if int(player['hp']) >= max_hp and int(player['mana']) >= max_mana:
            raise ActionRejected('inn_rest_not_needed')
        changed = conn.execute('''UPDATE players SET hp=?, mana=?, gold=gold-12
            WHERE telegram_id=? AND gold>=12''', (max_hp, max_mana, player_id))
        if changed.rowcount != 1:
            raise ActionRejected('inn_no_gold')
        result = {'schema_version':1,'action_kind':'inn','status':'rested','player_id':player_id,
                  'location_id':player['location_id'],'recipe_id':None,'consumed':[],'granted':[],
                  'gold_delta':-12,'gold_after':int(player['gold'])-12,'progression':[],
                  'source':{'service':'inn'},'details':{'hp_after':max_hp,'mana_after':max_mana}}
        store_receipt(conn, player_id, request_id, 'inn', request_hash, result)
        conn.commit(); return result
    except ActionRejected as exc:
        status = str(exc)
        if authorized and status != 'stale_action':
            player = conn.execute('SELECT location_id, gold FROM players WHERE telegram_id=?', (player_id,)).fetchone()
            result = store_business_rejection(
                conn, player_id=player_id, request_id=request_id, action_kind='inn',
                request_hash=request_hash, status=status,
                location_id=player['location_id'] if player else None,
                gold_after=player['gold'] if player else 0, source={'service': 'inn'},
            )
            conn.commit(); return result
        conn.rollback(); return {'status':status}
    except Exception:
        conn.rollback(); raise
    finally:
        conn.close()


def gift_inventory_item(sender_id: int, action_token: str) -> dict:
    from database import get_connection
    from game.action_receipts import ActionRejected, consume_action, peaceful_player
    request_id = f'ui:{action_token}'
    conn = get_connection()
    authorized = False
    request_hash = intent_hash('gift', sender_id, {})
    try:
        conn.execute('BEGIN IMMEDIATE')
        token_row = conn.execute("SELECT payload FROM player_ui_actions WHERE token=? AND player_id=? AND kind='gift'",
                                 (action_token, sender_id)).fetchone()
        payload = json.loads(token_row['payload']) if token_row else {}
        request_hash = intent_hash('gift', sender_id, payload)
        recovered = find_receipt(conn, sender_id, request_id, 'gift', request_hash)
        if recovered is not None:
            conn.commit(); return {**recovered, 'recovered':True}
        raw = consume_action(conn, sender_id, 'gift', action_token)
        authorized = True
        payload = json.loads(raw)
        sender = peaceful_player(conn, sender_id)
        recipient_id = int(payload['recipient_id'])
        if recipient_id == sender_id:
            raise ActionRejected('self_gift')
        if not conn.execute('SELECT 1 FROM players WHERE telegram_id=?', (recipient_id,)).fetchone():
            raise ActionRejected('stale_action')
        row = conn.execute('SELECT * FROM inventory WHERE id=? AND telegram_id=?',
                           (int(payload['inventory_id']), sender_id)).fetchone()
        if (not row or row['item_id'] != payload['item_id'] or int(row['quantity']) != int(payload['quantity'])
                or int(row['enhance_level']) != int(payload['enhance_level'])
                or int(row['durability']) != int(payload['durability'])):
            raise ActionRejected('stale_action')
        equipped = conn.execute('''SELECT 1 FROM equipment WHERE telegram_id=? AND
            (weapon=? OR offhand=? OR helmet=? OR chest=? OR legs=? OR boots=? OR gloves=? OR ring1=? OR ring2=? OR amulet=?)''',
            (sender_id,) + (row['id'],) * 10).fetchone()
        if equipped:
            raise ActionRejected('equipped_item')
        target = conn.execute('''SELECT id FROM inventory WHERE telegram_id=? AND item_id=?
            AND enhance_level=? AND durability=? ORDER BY id LIMIT 1''',
            (recipient_id, row['item_id'], row['enhance_level'], row['durability'])).fetchone()
        if target:
            conn.execute('UPDATE inventory SET quantity=quantity+1 WHERE id=?', (target['id'],))
        else:
            conn.execute('''INSERT INTO inventory(telegram_id,item_id,quantity,enhance_level,durability)
                VALUES (?,?,1,?,?)''', (recipient_id,row['item_id'],row['enhance_level'],row['durability']))
        changed = conn.execute('''UPDATE inventory SET quantity=quantity-1 WHERE id=? AND telegram_id=? AND quantity=?''',
                               (row['id'], sender_id, row['quantity']))
        if changed.rowcount != 1:
            raise RuntimeError('gift_sender_debit_failed')
        conn.execute('DELETE FROM inventory WHERE id=? AND quantity=0', (row['id'],))
        result={'schema_version':1,'action_kind':'gift','status':'gifted','player_id':sender_id,
                'location_id':sender['location_id'],'recipe_id':None,
                'consumed':[{'item_id':row['item_id'],'quantity':1}],
                'granted':[{'item_id':row['item_id'],'quantity':1,'recipient_id':recipient_id,'instance_ids':[],'gear_specs':[]}],
                'gold_delta':0,'gold_after':sender['gold'],'progression':[],
                'source':{'recipient_id':recipient_id},'details':{}}
        store_receipt(conn,sender_id,request_id,'gift',request_hash,result)
        conn.commit(); return result
    except ActionRejected as exc:
        status = str(exc)
        if authorized and status != 'stale_action':
            sender = conn.execute('SELECT location_id, gold FROM players WHERE telegram_id=?', (sender_id,)).fetchone()
            result = store_business_rejection(
                conn, player_id=sender_id, request_id=request_id, action_kind='gift',
                request_hash=request_hash, status=status,
                location_id=sender['location_id'] if sender else None,
                gold_after=sender['gold'] if sender else 0,
                source={'recipient_id': payload.get('recipient_id')},
            )
            conn.commit(); return result
        conn.rollback(); return {'status':status}
    except Exception:
        conn.rollback(); raise
    finally:
        conn.close()
