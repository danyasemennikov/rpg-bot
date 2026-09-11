"""Persistence and revision-bound mutations for reliable gear progression."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from database import get_connection
from game.action_receipts import ActionRejected, consume_action, issue_actions, peaceful_player
from game.field_catalog import FIELD_ITEM_IDS, FIELD_MAX_TIER, is_field_item
from game.gear_instances import (
    MAX_ENHANCE_LEVEL,
    get_enhance_requirements_for_target_level,
    resolve_enhancement_attempt_outcome,
)
from game.items_data import get_item, get_item_metadata
from game.tier_advancement import resolve_advancement_cost


def _columns(conn, table_name: str) -> set[str]:
    return {str(row['name']) for row in conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()}


def _add_column(conn, table_name: str, column_name: str, sql: str) -> None:
    if column_name not in _columns(conn, table_name):
        conn.execute(f'ALTER TABLE {table_name} ADD COLUMN {column_name} {sql}')


def ensure_gear_progression_schema(conn) -> None:
    """Idempotent additive migration; never rewrites existing item instances."""
    _add_column(conn, 'players', 'gear_revision', 'INTEGER NOT NULL DEFAULT 0')
    _add_column(conn, 'gear_instances', 'revision', 'INTEGER NOT NULL DEFAULT 0')
    _add_column(conn, 'gear_instances', 'source_settlement_id', 'TEXT')
    _add_column(conn, 'gear_instances', 'source_metadata_json', "TEXT NOT NULL DEFAULT '{}'")
    conn.execute('''CREATE TABLE IF NOT EXISTS player_gear_progress (
        player_id INTEGER NOT NULL REFERENCES players(telegram_id),
        route_id TEXT NOT NULL,
        dry_streak INTEGER NOT NULL DEFAULT 0 CHECK (dry_streak BETWEEN 0 AND 11),
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (player_id, route_id)
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS player_gear_goals (
        player_id INTEGER PRIMARY KEY REFERENCES players(telegram_id),
        base_item_id TEXT NOT NULL REFERENCES items(item_id),
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS pve_reward_settlements (
        encounter_id TEXT PRIMARY KEY,
        schema_version INTEGER NOT NULL,
        policy_version TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('prepared', 'applied', 'legacy_review')),
        plan_json TEXT NOT NULL,
        result_json TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        applied_at TEXT
    )''')
    conn.execute('''CREATE INDEX IF NOT EXISTS idx_pve_reward_settlements_status
        ON pve_reward_settlements(status, updated_at)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS gear_mutation_receipts (
        action_token TEXT PRIMARY KEY,
        player_id INTEGER NOT NULL REFERENCES players(telegram_id),
        action_kind TEXT NOT NULL,
        result_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.execute('''CREATE INDEX IF NOT EXISTS idx_gear_mutation_receipts_player
        ON gear_mutation_receipts(player_id, created_at)''')


def get_equipment_goal(player_id: int) -> str | None:
    conn = get_connection()
    try:
        row = conn.execute('SELECT base_item_id FROM player_gear_goals WHERE player_id=?', (player_id,)).fetchone()
        return str(row['base_item_id']) if row else None
    finally:
        conn.close()


def set_equipment_goal(player_id: int, base_item_id: str | None) -> bool:
    if base_item_id is not None and base_item_id not in FIELD_ITEM_IDS:
        return False
    conn = get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        if not conn.execute('SELECT 1 FROM players WHERE telegram_id=?', (player_id,)).fetchone():
            conn.rollback()
            return False
        if base_item_id is None:
            conn.execute('DELETE FROM player_gear_goals WHERE player_id=?', (player_id,))
        else:
            conn.execute('''INSERT INTO player_gear_goals(player_id, base_item_id, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP) ON CONFLICT(player_id) DO UPDATE SET
                base_item_id=excluded.base_item_id, updated_at=CURRENT_TIMESTAMP''',
                (player_id, base_item_id))
        conn.commit()
        return True
    finally:
        conn.close()


def _json_payload(**values: Any) -> str:
    return json.dumps(values, separators=(',', ':'), sort_keys=True)


def _next_live_tier(current_tier: int) -> int | None:
    return next((tier for tier in (5, 10, 15, 20) if tier > max(1, int(current_tier))), None)


def build_gear_mutation_preview(player_id: int, action: str, instance_id: int,
                                *, target_slot: str | None = None) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute('''SELECT g.*, p.gear_revision FROM gear_instances g
            JOIN players p ON p.telegram_id=g.telegram_id
            WHERE g.id=? AND g.telegram_id=?''', (instance_id, player_id)).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    instance = dict(row)
    item = get_item(str(instance['base_item_id'])) or {}
    cost_ref: dict[str, Any] = {}
    if action == 'sale':
        cost_ref = {'gold': 5 if is_field_item(str(instance['base_item_id'])) else int(item.get('sell_price', 0))}
    elif action == 'enhance':
        current = max(0, int(instance.get('enhance_level', 0)))
        if current >= MAX_ENHANCE_LEVEL:
            return None
        cost_ref = dict(get_enhance_requirements_for_target_level(current + 1))
        cost_ref['target_level'] = current + 1
    elif action == 'advance':
        target = _next_live_tier(int(instance.get('item_tier', 1)))
        if target is None or str(instance.get('rarity') or '') == 'unique':
            return None
        cost = resolve_advancement_cost(
            current_tier=int(instance.get('item_tier', 1)),
            target_tier=target,
            rarity=str(instance.get('rarity') or 'common'),
        )
        cost_ref = {**asdict(cost), 'target_tier': target}
    elif action not in {'equip', 'unequip'}:
        return None
    payload = _json_payload(
        action=action,
        instance_id=int(instance['id']),
        instance_revision=int(instance['revision']),
        gear_revision=int(instance['gear_revision']),
        target_slot=target_slot,
        cost_ref=cost_ref,
    )
    return {'instance': instance, 'cost': cost_ref, 'payload': payload}


def issue_gear_intent(player_id: int, action: str, instance_id: int, *, target_slot: str | None = None) -> str | None:
    preview = build_gear_mutation_preview(player_id, action, instance_id, target_slot=target_slot)
    if not preview:
        return None
    payload = str(preview['payload'])
    return issue_actions(player_id, f'gear_{action}', [payload]).get(payload)


def _load_intent(conn, player_id: int, action: str, token: str) -> tuple[dict, dict, dict]:
    player = peaceful_player(conn, player_id, service='craftsmen_guild' if action == 'advance' else None)
    raw = consume_action(conn, player_id, f'gear_{action}', token)
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ActionRejected('stale_action') from exc
    if not isinstance(payload, dict) or payload.get('action') != action:
        raise ActionRejected('stale_action')
    row = conn.execute('SELECT * FROM gear_instances WHERE id=? AND telegram_id=?',
                       (int(payload.get('instance_id', 0)), player_id)).fetchone()
    if not row:
        raise ActionRejected('stale_action')
    instance = dict(row)
    if int(instance.get('revision', 0)) != int(payload.get('instance_revision', -1)):
        raise ActionRejected('stale_action')
    if int(player.get('gear_revision', 0)) != int(payload.get('gear_revision', -1)):
        raise ActionRejected('stale_action')
    return player, instance, payload


def _consume_stack(conn, player_id: int, item_id: str, quantity: int) -> None:
    row = conn.execute('''SELECT id, quantity FROM inventory WHERE telegram_id=? AND item_id=?
        ORDER BY id LIMIT 1''', (player_id, item_id)).fetchone()
    if not row or int(row['quantity']) < quantity:
        raise ActionRejected('no_material')
    remaining = int(row['quantity']) - quantity
    if remaining:
        conn.execute('UPDATE inventory SET quantity=? WHERE id=?', (remaining, row['id']))
    else:
        conn.execute('DELETE FROM inventory WHERE id=?', (row['id'],))


def _clamp_with_conn(conn, player_id: int) -> None:
    from game.equipment_stats import clamp_player_resources_to_effective_caps
    clamp_player_resources_to_effective_caps(player_id, conn=conn)


def apply_gear_intent(player_id: int, action: str, token: str, *, rng_roll: float | None = None,
                      failure_hook=None) -> dict:
    """Consume one preview intent and mutate exactly once inside one write transaction."""
    conn = get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        player, instance, payload = _load_intent(conn, player_id, action, token)
        item = get_item(str(instance['base_item_id'])) or {}
        instance_id = int(instance['id'])

        if action == 'equip':
            slot = str(payload.get('target_slot') or '')
            identity = str(get_item_metadata(str(instance['base_item_id'])).get('slot_identity') or '')
            if identity != slot and not (identity == 'ring' and slot in {'ring1', 'ring2'}):
                raise ActionRejected('wrong_equipment_slot')
            for stat in ('level', 'strength', 'agility', 'intuition', 'wisdom'):
                if int(player.get(stat, 0)) < int(item.get(f'req_{stat}', 0)):
                    raise ActionRejected('equipment_requirements')
            conn.execute(f'UPDATE equipment SET {slot}=NULL WHERE telegram_id=?', (player_id,))
            conn.execute('UPDATE gear_instances SET equipped_slot=NULL, revision=revision+1 '
                         'WHERE telegram_id=? AND equipped_slot=?', (player_id, slot))
            conn.execute('UPDATE gear_instances SET equipped_slot=?, revision=revision+1 WHERE id=? AND telegram_id=?',
                         (slot, instance_id, player_id))
            conn.execute('UPDATE players SET gear_revision=gear_revision+1 WHERE telegram_id=?', (player_id,))
            _clamp_with_conn(conn, player_id)
            result = {'status': 'equipped', 'instance_id': instance_id, 'slot': slot}

        elif action == 'sale':
            if instance.get('equipped_slot'):
                raise ActionRejected('equipped_item')
            price = 5 if is_field_item(str(instance['base_item_id'])) else int(item.get('sell_price', 0))
            if payload.get('cost_ref') != {'gold': price}:
                raise ActionRejected('stale_action')
            if price <= 0:
                raise ActionRejected('not_sellable')
            conn.execute('DELETE FROM gear_instances WHERE id=? AND telegram_id=?', (instance_id, player_id))
            if failure_hook:
                failure_hook('after_gear_deletion')
            conn.execute('UPDATE players SET gold=gold+?, gear_revision=gear_revision+1 WHERE telegram_id=?',
                         (price, player_id))
            result = {'status': 'sold', 'instance_id': instance_id, 'gold': price}

        elif action == 'enhance':
            current = max(0, int(instance.get('enhance_level', 0)))
            if current >= MAX_ENHANCE_LEVEL:
                raise ActionRejected('max_level')
            req = get_enhance_requirements_for_target_level(current + 1)
            expected_cost = {**dict(req), 'target_level': current + 1}
            if payload.get('cost_ref') != expected_cost:
                raise ActionRejected('stale_action')
            if int(player['gold']) < int(req['gold']):
                raise ActionRejected('no_gold')
            conn.execute('UPDATE players SET gold=gold-? WHERE telegram_id=?', (req['gold'], player_id))
            _consume_stack(conn, player_id, str(req['material_id']), int(req['material_qty']))
            if failure_hook:
                failure_hook('after_material_deduction')
            outcome = resolve_enhancement_attempt_outcome(current, rng_roll=rng_roll)
            after: int | None = current
            if outcome == 'success':
                after = current + 1
            elif outcome == 'rollback':
                after = max(0, current - 1)
            elif outcome == 'break':
                after = None
                conn.execute('DELETE FROM gear_instances WHERE id=? AND telegram_id=?', (instance_id, player_id))
            if after is not None:
                conn.execute('UPDATE gear_instances SET enhance_level=?, revision=revision+1 WHERE id=? AND telegram_id=?',
                             (after, instance_id, player_id))
            conn.execute('UPDATE players SET gear_revision=gear_revision+1 WHERE telegram_id=?', (player_id,))
            _clamp_with_conn(conn, player_id)
            result = {'status': 'enhanced', 'outcome': outcome, 'instance_id': instance_id,
                      'before': current, 'after': after, 'cost': req}

        elif action == 'advance':
            current = max(1, int(instance.get('item_tier', 1)))
            target = _next_live_tier(current)
            if target is None or target > FIELD_MAX_TIER:
                raise ActionRejected('max_tier')
            rarity = str(instance.get('rarity') or 'common')
            if rarity == 'unique':
                raise ActionRejected('not_eligible')
            cost = resolve_advancement_cost(current_tier=current, target_tier=target, rarity=rarity)
            expected_cost = {**asdict(cost), 'target_tier': target}
            if payload.get('cost_ref') != expected_cost:
                raise ActionRejected('stale_action')
            if int(player['gold']) < cost.gold:
                raise ActionRejected('no_gold')
            conn.execute('UPDATE players SET gold=gold-? WHERE telegram_id=?', (cost.gold, player_id))
            _consume_stack(conn, player_id, cost.material_id, cost.material_qty)
            conn.execute('UPDATE gear_instances SET item_tier=?, revision=revision+1 WHERE id=? AND telegram_id=?',
                         (target, instance_id, player_id))
            conn.execute('UPDATE players SET gear_revision=gear_revision+1 WHERE telegram_id=?', (player_id,))
            _clamp_with_conn(conn, player_id)
            result = {'status': 'advanced', 'instance_id': instance_id, 'before': current,
                      'after': target, 'cost': asdict(cost)}
        elif action == 'unequip':
            slot = str(instance.get('equipped_slot') or '')
            if not slot or (payload.get('target_slot') and str(payload.get('target_slot')) != slot):
                raise ActionRejected('stale_action')
            conn.execute('UPDATE gear_instances SET equipped_slot=NULL, revision=revision+1 '
                         'WHERE id=? AND telegram_id=? AND equipped_slot=?',
                         (instance_id, player_id, slot))
            conn.execute('UPDATE players SET gear_revision=gear_revision+1 WHERE telegram_id=?', (player_id,))
            _clamp_with_conn(conn, player_id)
            result = {'status': 'unequipped', 'instance_id': instance_id, 'slot': slot}
        else:
            raise ActionRejected('stale_action')

        conn.execute('''INSERT INTO gear_mutation_receipts
            (action_token, player_id, action_kind, result_json) VALUES (?, ?, ?, ?)''',
            (token, player_id, action, json.dumps(result, ensure_ascii=False, sort_keys=True)))
        conn.commit()
        return result
    except ActionRejected as exc:
        conn.rollback()
        return {'status': str(exc)}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def exchange_enhancement_crystal(player_id: int, action_token: str) -> dict:
    """10 shards + 25 gold -> one crystal, after the Homecoming chapter."""
    from game.gear_instances import grant_item_to_player
    conn = get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        player = peaceful_player(conn, player_id, service='craftsmen_guild')
        consume_action(conn, player_id, 'gear_crystal_exchange', action_token, payload='10:25')
        unlocked = conn.execute('''SELECT 1 FROM player_contract_history
            WHERE player_id=? AND contract_key='chapter_homecoming' ''', (player_id,)).fetchone()
        if not unlocked:
            raise ActionRejected('chapter_required')
        if int(player['gold']) < 25:
            raise ActionRejected('no_gold')
        _consume_stack(conn, player_id, 'enhance_shard', 10)
        conn.execute('UPDATE players SET gold=gold-25 WHERE telegram_id=?', (player_id,))
        result = grant_item_to_player(player_id, 'enhancement_crystal', quantity=1, conn=conn)
        if int(result.get('stackable_added', 0)) != 1:
            raise RuntimeError('item_delivery_mismatch')
        conn.execute('''INSERT INTO gear_mutation_receipts
            (action_token, player_id, action_kind, result_json) VALUES (?, ?, 'crystal_exchange', ?)''',
            (action_token, player_id, json.dumps({'status': 'exchanged'}, sort_keys=True)))
        conn.commit()
        return {'status': 'exchanged'}
    except ActionRejected as exc:
        conn.rollback()
        return {'status': str(exc)}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def issue_crystal_exchange_intent(player_id: int) -> str | None:
    return issue_actions(player_id, 'gear_crystal_exchange', ['10:25']).get('10:25')
