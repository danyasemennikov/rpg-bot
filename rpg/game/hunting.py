"""PEV1 owner-only harvesting authorized by an applied reward settlement."""

from __future__ import annotations

import json

from database import add_gathering_profession_exp, get_connection
from game.action_receipts import ActionRejected, consume_action, peaceful_player, require_item_delivery
from game.economy_actions import find_receipt, intent_hash, store_receipt
from game.gathering_progression import gathering_profession_xp_for_success
from game.gear_instances import grant_item_to_player
from game.locations import resolve_location_id
from game.profession_resources import HARVEST_MANIFEST, RESOURCES

# Compatibility name used by the battle result renderer; the manifest remains
# the one authoritative mob-to-output mapping.
HARVEST_ITEMS = HARVEST_MANIFEST


def _json(raw):
    try:
        value = json.loads(raw or '{}')
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _authority(conn, player_id: int, encounter_id: str) -> tuple[dict, dict, dict]:
    row = conn.execute('''SELECT e.*, s.schema_version, s.policy_version,
        s.status AS settlement_status, s.plan_json, s.result_json
        FROM pve_encounters e JOIN pve_reward_settlements s ON s.encounter_id=e.encounter_id
        WHERE e.encounter_id=? AND e.owner_player_id=? AND e.status='victory' ''',
        (encounter_id, player_id)).fetchone()
    if not row or row['settlement_status'] != 'applied':
        raise ActionRejected('harvest_not_applied')
    if int(row['schema_version']) != 1 or row['policy_version'] not in {'legacy_v0', 'field_loot_v1'}:
        raise ActionRejected('harvest_unknown_authority')
    plan, result = _json(row['plan_json']), _json(row['result_json'])
    if (str(plan.get('encounter_id')) != encounter_id
            or int(plan.get('owner_player_id', 0)) != player_id
            or resolve_location_id(plan.get('location_id')) != resolve_location_id(row['location_id'])):
        raise ActionRejected('harvest_identity_mismatch')
    eligible = {int(value) for value in plan.get('eligible_recipient_ids') or []}
    defeated = {int(value) for value in plan.get('defeated_participant_ids') or []}
    recipients = {int(value.get('player_id', 0)) for value in result.get('recipients') or []}
    if player_id not in eligible or player_id in defeated or player_id not in recipients:
        raise ActionRejected('harvest_owner_defeated')
    return dict(row), plan, result


def _choices(plan: dict) -> list[dict]:
    choices, seen = [], set()
    for unit in sorted(plan.get('enemy_units') or [], key=lambda value: str(value.get('unit_id') or '')):
        mob_id, unit_id = str(unit.get('mob_id') or ''), str(unit.get('unit_id') or '')
        for item_id in HARVEST_MANIFEST.get(mob_id, ()):
            key = (mob_id, item_id)
            if not unit_id or key in seen:
                continue
            seen.add(key)
            choices.append({'unit_id': unit_id, 'mob_id': mob_id, 'item_id': item_id})
    return choices


def harvestable_victory_page(player_id: int, *, page: int = 0,
                             page_size: int = 5) -> tuple[list[dict], int, int]:
    conn = get_connection()
    try:
        player = conn.execute('SELECT location_id FROM players WHERE telegram_id=?', (player_id,)).fetchone()
        if not player or not conn.execute("SELECT 1 FROM sqlite_master WHERE name='pve_reward_settlements'").fetchone():
            return [], 0, 1
        rows = conn.execute('''SELECT e.encounter_id, e.location_id FROM pve_encounters e
            JOIN pve_reward_settlements s ON s.encounter_id=e.encounter_id
            LEFT JOIN pve_harvest_claims h ON h.encounter_id=e.encounter_id AND h.player_id=?
            WHERE e.owner_player_id=? AND e.status='victory' AND s.status='applied'
              AND h.encounter_id IS NULL AND e.finished_at >= datetime('now', '-30 minutes')
              ORDER BY e.finished_at DESC''', (player_id, player_id)).fetchall()
        output = []
        for row in rows:
            if resolve_location_id(row['location_id']) != resolve_location_id(player['location_id']):
                continue
            try:
                encounter, plan, _ = _authority(conn, player_id, row['encounter_id'])
            except ActionRejected:
                continue
            output.extend({'encounter_id': encounter['encounter_id'], 'location_id': encounter['location_id'], **choice}
                          for choice in _choices(plan))
        pages = max(1, (len(output) + page_size - 1) // page_size)
        page = min(max(0, int(page)), pages - 1)
        start = page * page_size
        return output[start:start + page_size], page, pages
    finally:
        conn.close()


def list_harvestable_victories(player_id: int, *, page: int = 0, page_size: int = 5) -> list[dict]:
    return harvestable_victory_page(player_id, page=page, page_size=page_size)[0]


def harvest_victory(player_id: int, encounter_id: str, *, unit_id: str | None = None,
                    item_id: str | None = None, action_token: str | None = None,
                    request_id: str | None = None) -> dict:
    conn = get_connection()
    authorized = False
    receipt_hash = ''
    try:
        conn.execute('BEGIN IMMEDIATE')
        if action_token:
            request_id = request_id or f'ui:{action_token}'
            token = conn.execute("SELECT payload FROM player_ui_actions WHERE token=? AND player_id=? AND kind='harvest'",
                                 (action_token, player_id)).fetchone()
            if token:
                payload = _json(token['payload'])
                encounter_id = str(payload.get('encounter_id') or encounter_id)
                unit_id = str(payload.get('unit_id') or unit_id or '')
                item_id = str(payload.get('item_id') or item_id or '')
        parameters = {'encounter_id': encounter_id, 'unit_id': unit_id, 'item_id': item_id}
        receipt_hash = intent_hash('harvest', player_id, parameters)
        if request_id:
            recovered = find_receipt(conn, player_id, request_id, 'harvest', receipt_hash)
            if recovered is not None:
                conn.commit()
                return {**recovered, 'recovered': True}
        if action_token:
            consume_action(conn, player_id, 'harvest', action_token,
                           payload=json.dumps(parameters, sort_keys=True, separators=(',', ':')))
            authorized = True
        player = peaceful_player(conn, player_id)
        encounter, plan, _ = _authority(conn, player_id, encounter_id)
        if resolve_location_id(encounter['location_id']) != resolve_location_id(player['location_id']):
            raise ActionRejected('wrong_location')
        age = conn.execute("SELECT (julianday('now')-julianday(?))*86400 AS seconds", (encounter['finished_at'],)).fetchone()['seconds']
        if age is None or not 0 <= float(age) <= 1800:
            raise ActionRejected('harvest_expired')
        choices = _choices(plan)
        if unit_id is None and item_id is None and choices:
            unit_id, item_id = choices[0]['unit_id'], choices[0]['item_id']
        choice = next((value for value in choices if value['unit_id'] == unit_id and value['item_id'] == item_id), None)
        if not choice:
            raise ActionRejected('harvest_invalid_choice')
        conn.execute("INSERT OR IGNORE INTO player_gathering_professions(telegram_id, profession_key) VALUES (?, 'hunting')", (player_id,))
        state = conn.execute("SELECT level FROM player_gathering_professions WHERE telegram_id=? AND profession_key='hunting'", (player_id,)).fetchone()
        required = RESOURCES[item_id].required_level
        if int(state['level']) < required:
            raise ActionRejected('profession_locked')
        inserted = conn.execute('INSERT OR IGNORE INTO pve_harvest_claims(encounter_id, player_id, item_id) VALUES (?, ?, ?)',
                                (encounter_id, player_id, item_id))
        if inserted.rowcount != 1:
            raise ActionRejected('stale_action')
        require_item_delivery(grant_item_to_player(player_id, item_id, 1, source='hunting', conn=conn), 1)
        xp = gathering_profession_xp_for_success(current_profession_level=state['level'], required_profession_level=required)
        progression = add_gathering_profession_exp(player_id, 'hunting', xp, conn=conn)
        from game.quest_board import register_contract_objective
        register_contract_objective(conn, player_id, 'harvest', item_id, 1, player['location_id'])
        result = {'schema_version': 1, 'action_kind': 'harvest', 'status': 'harvested',
                  'player_id': player_id, 'location_id': player['location_id'], 'recipe_id': None,
                  'consumed': [], 'granted': [{'item_id': item_id, 'quantity': 1, 'instance_ids': [], 'gear_specs': []}],
                  'gold_delta': 0, 'gold_after': player['gold'],
                  'progression': [{'profession_key': 'hunting', 'old_level': progression.old_level,
                    'old_exp': progression.old_exp, 'new_level': progression.new_level,
                    'new_exp': progression.new_exp, 'xp_awarded': progression.xp_awarded}],
                  'source': {'encounter_id': encounter_id, **choice}, 'details': {}}
        if request_id:
            store_receipt(conn, player_id, request_id, 'harvest', receipt_hash, result)
        conn.commit()
        return {**result, 'item_id': item_id, 'progression_result': progression}
    except ActionRejected as exc:
        status = str(exc)
        if authorized and request_id and status != 'stale_action':
            from game.economy_actions import store_business_rejection
            player = conn.execute('SELECT location_id, gold FROM players WHERE telegram_id=?', (player_id,)).fetchone()
            result = store_business_rejection(
                conn, player_id=player_id, request_id=request_id, action_kind='harvest',
                request_hash=receipt_hash, status=status,
                location_id=player['location_id'] if player else None,
                gold_after=player['gold'] if player else 0,
                source={'encounter_id': encounter_id, 'unit_id': unit_id, 'item_id': item_id},
            )
            conn.commit()
            return result
        conn.rollback()
        return {'status': status}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
