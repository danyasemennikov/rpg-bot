"""Durable order/result receipts shared by PvE and PvP V1."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from database import get_connection
from game.action_receipts import ActionRejected, consume_action, issue_actions
from game.build_contract import RULES_VERSION
from game.build_progression import ensure_build_schema


COMBAT_UI_ACTION_KIND = "combat_v1"
COMBAT_ACK_KIND = 'combat_order_ack_pxe1'


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def issue_combat_intents(
    player_id: int, *, encounter_id: str, turn_revision: int,
    deadline_at: str, actions: list[dict[str, Any]], encounter_kind: str = "pve",
) -> dict[str, str]:
    """Issue compact callback tokens for complete encounter/revision intents."""
    payloads = [
        _stable_json({
            "rules_version": RULES_VERSION,
            "encounter_kind": str(encounter_kind),
            "encounter_id": str(encounter_id),
            "turn_revision": int(turn_revision),
            "actor_id": int(player_id),
            "deadline_at": str(deadline_at),
            "action": action,
            "target_id": action.get("target_id", (action.get("target_info") or {}).get("id")),
        })
        for action in actions
    ]
    raw_tokens = issue_actions(player_id, COMBAT_UI_ACTION_KIND, payloads)
    return {
        _stable_json(action): raw_tokens[payload]
        for action, payload in zip(actions, payloads)
        if payload in raw_tokens
    }


def consume_combat_intent(player_id: int, token: str) -> dict[str, Any]:
    """Atomically consume, revalidate and durably commit one UI order."""
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        ensure_build_schema(conn)
        recovered = _recover_combat_ack(conn,player_id,token)
        if recovered:
            conn.rollback()
            return recovered
        try:
            raw = consume_action(conn, player_id, COMBAT_UI_ACTION_KIND, token)
            payload = json.loads(raw)
        except (ActionRejected, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ActionRejected("stale_action") from exc
        if (
            not isinstance(payload, dict)
            or payload.get("rules_version") != RULES_VERSION
            or payload.get("encounter_kind") not in {"pve", "pvp"}
            or int(payload.get("actor_id", 0)) != int(player_id)
        ):
            raise ActionRejected("stale_action")
        encounter_kind = str(payload.get("encounter_kind"))
        encounter_id = str(payload.get("encounter_id") or "")
        revision = int(payload.get("turn_revision", -1))
        if encounter_kind == "pve":
            encounter = conn.execute('''SELECT *
                FROM pve_encounters WHERE encounter_id=?''', (encounter_id,)).fetchone()
            participant = conn.execute('''SELECT status FROM pve_encounter_participants
                WHERE encounter_id=? AND player_id=?''', (encounter_id, player_id)).fetchone()
            valid_encounter = bool(
                encounter and str(encounter["status"]) == "active"
                and participant and str(participant["status"]) == "active"
            )
        else:
            if not encounter_id.isdigit():
                raise ActionRejected("stale_action")
            encounter = conn.execute('''SELECT *,engagement_state AS status
                FROM pvp_engagements WHERE id=?''', (int(encounter_id),)).fetchone()
            valid_encounter = bool(
                encounter and str(encounter["status"]) == "converted_to_battle"
                and int(player_id) in {int(encounter["attacker_id"]), int(encounter["defender_id"])}
            )
            if encounter and encounter['world_model_version'] == 1:
                from game.pvp_group_runtime import authorize_order
                battle = json.loads(encounter['reason_context']).get('battle') or {}
                if revision != int(battle.get('turn_revision',-1)):
                    raise ActionRejected('stale_action')
                authorize_order(conn,encounter,battle,player_id,payload.get('action') or {},deadline_at=payload.get('deadline_at'))
                valid_encounter = True
        if (
            not valid_encounter
            or str(encounter["rules_version"]) != RULES_VERSION
            or int(encounter["turn_revision"]) not in {revision, revision - 1}
        ):
            raise ActionRejected("stale_action")
        raw_deadline = str(payload.get("deadline_at") or "")
        try:
            deadline = datetime.fromisoformat(raw_deadline.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ActionRejected("stale_action") from exc
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) >= deadline.astimezone(timezone.utc):
            raise ActionRejected("deadline_elapsed")
        action = payload.get("action")
        if not isinstance(action, dict):
            raise ActionRejected("stale_action")
        target_id = payload.get("target_id")
        if action.get("kind") != "flee":
            if encounter_kind=='pve' and 'lifecycle_version' in encounter.keys() and encounter['lifecycle_version']==1:
                _validate_pxe1_pve_order(conn,encounter,player_id,action)
            durable = submit_combat_order(
                encounter_kind=encounter_kind, encounter_id=encounter_id,
                turn_revision=revision, actor_id=player_id, action=action,
                target_id=target_id, deadline_at=raw_deadline, order_kind="manual",
                conn=conn,
            )
            if not durable.get("accepted"):
                raise ActionRejected(str(durable.get("reason") or "stale_action"))
            pxe1 = ('lifecycle_version' in encounter.keys() and encounter['lifecycle_version']==1) if encounter_kind=='pve' else ('world_model_version' in encounter.keys() and encounter['world_model_version']==1)
            if pxe1:
                from game.economy_actions import intent_hash,store_receipt
                actor = conn.execute('SELECT location_id,gold FROM players WHERE telegram_id=?',(player_id,)).fetchone()
                result = {'schema_version':1,'catalog_version':2,'action_kind':COMBAT_ACK_KIND,
                    'status':'ordered','player_id':player_id,'location_id':actor['location_id'],'recipe_id':None,
                    'consumed':[],'granted':[],'gold_delta':0,'gold_after':actor['gold'],'progression':[],
                    'source':{'intent':payload},'details':{'accepted':True,**payload}}
                store_receipt(conn,player_id,'ui:'+token,COMBAT_ACK_KIND,intent_hash(COMBAT_ACK_KIND,player_id,payload),result,catalog_version=2)
        conn.commit()
        return {"accepted": True, **payload}
    except ActionRejected as exc:
        conn.rollback()
        return {"accepted": False, "reason": str(exc)}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _recover_combat_ack(conn,player_id,token):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='economy_action_receipts'").fetchone():
        return None
    row = conn.execute('SELECT * FROM economy_action_receipts WHERE player_id=? AND request_id=? AND action_kind=?',
                       (player_id,'ui:'+token,COMBAT_ACK_KIND)).fetchone()
    if not row:
        return None
    from game.economy_actions import intent_hash
    try:
        result=json.loads(row['result_json'])
        intent=result['source']['intent']
        if (result['player_id']!=player_id or intent['actor_id']!=player_id
                or result['action_kind']!=COMBAT_ACK_KIND or result['status']!='ordered'
                or result['schema_version']!=1 or result['catalog_version']!=2
                or row['request_hash']!=intent_hash(COMBAT_ACK_KIND,player_id,intent)
                or result['details']!={'accepted':True,**intent}):
            raise ValueError()
        return {**result['details'],'already_applied':True}
    except (ValueError,TypeError,KeyError):
        raise ActionRejected('stale_action')


def _validate_pxe1_pve_order(conn,encounter,player_id,action):
    from game.build_contract import POWER_STRIKE,SKILL_SPECS
    from game.combat_identity import evaluate_action
    state=json.loads(encounter['battle_state_json'])
    active_ids={str(r['player_id']) for r in conn.execute("SELECT player_id FROM pve_encounter_participants WHERE encounter_id=? AND status='active'",(encounter['encounter_id'],))}
    actors=state.get('participant_states_v1') or {}
    actor=actors.get(str(player_id))
    if not actor or state.get('active_side')!='side_a' or str(player_id) not in active_ids:
        raise ActionRejected('not_your_turn')
    allies=[entity for key,entity in actors.items() if key in active_ids]
    enemies=state.get('enemy_states_v1') or []
    kind=action.get('kind')
    if action.get('target_info') is not None and not isinstance(action['target_info'],dict):
        raise ActionRejected('invalid_target')
    target=(action.get('target_info') or {}).get('id',action.get('target_id'))
    target=str(target) if target is not None else None
    live_allies={str(a['actor_id']) for a in allies if int(a['hp'])>0 and not a.get('dead')}
    live_enemies={str(e['unit_id']) for e in enemies if int(e['hp'])>0 and not e.get('dead')}
    if kind=='basic_attack':
        if target not in live_enemies: raise ActionRejected('invalid_target')
        selected={'kind':'normal','target_id':target,'manual':True}
    elif kind=='guard':
        if target not in {None,str(player_id)}: raise ActionRejected('invalid_target')
        selected={'kind':'guard','target_id':player_id,'manual':True}
    elif kind=='skill':
        spec=POWER_STRIKE if action.get('skill_id')=='power_strike' else SKILL_SPECS.get(action.get('skill_id'))
        if not spec: raise ActionRejected('invalid_action')
        allowed=live_allies if spec.target=='Ally' else live_allies|live_enemies if spec.target=='AllyOrEnemy' else live_enemies
        if spec.target in {'S','B','Ally','AllyOrEnemy'} and target not in allowed:
            raise ActionRejected('invalid_target')
        if spec.target=='Self' and target not in {None,str(player_id)}:
            raise ActionRejected('invalid_target')
        if spec.target in {'Party','F','A','2x2'} and target is not None:
            raise ActionRejected('invalid_target')
        selected={'kind':'skill','skill_id':action['skill_id'],'target_id':target,'manual':True}
    else:
        raise ActionRejected('invalid_action')
    # The shared pure evaluator validates ranks, family, MP, cooldown and target
    # pattern under this writer. Discard its copies; the side owner applies once.
    result=evaluate_action(actor,allies,enemies,selected,rng_seed=0,side_index=state.get('turn_revision',0))
    if not result['accepted']:
        raise ActionRejected(result.get('reason','invalid_action'))


def recover_combat_intent(player_id,token):
    """Read the original acknowledgment before current combat or UI state."""
    conn=get_connection()
    try:
        return _recover_combat_ack(conn,player_id,token)
    finally:
        conn.close()


def submit_combat_order(
    *,
    encounter_kind: str,
    encounter_id: str,
    turn_revision: int,
    actor_id: int,
    action: dict[str, Any],
    target_id: str | int | None,
    deadline_at: str,
    order_kind: str = "manual",
    conn=None,
) -> dict[str, Any]:
    """Insert one authoritative order; identical retries are acknowledged."""
    if encounter_kind not in {"pve", "pvp"}:
        return {"accepted": False, "reason": "unknown_encounter_kind"}
    owns = conn is None
    if owns:
        conn = get_connection()
        conn.execute("BEGIN IMMEDIATE")
    try:
        ensure_build_schema(conn)
        encoded = _stable_json(action)
        existing = conn.execute('''SELECT action_json, target_id, order_kind, rules_version
            FROM combat_orders_v1 WHERE encounter_kind=? AND encounter_id=?
            AND turn_revision=? AND actor_id=?''', (
                encounter_kind, encounter_id, int(turn_revision), int(actor_id),
            )).fetchone()
        normalized_target = None if target_id is None else str(target_id)
        if existing:
            identical = (
                str(existing["action_json"]) == encoded
                and existing["target_id"] == normalized_target
                and str(existing["order_kind"]) == order_kind
                and str(existing["rules_version"]) == RULES_VERSION
            )
            if owns:
                conn.rollback()
            return {"accepted": identical, "duplicate": identical, "reason": "duplicate" if identical else "conflicting_order"}
        result = conn.execute('''INSERT OR IGNORE INTO combat_orders_v1
            (encounter_kind, encounter_id, turn_revision, actor_id, action_json,
             target_id, rules_version, deadline_at, order_kind)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
                encounter_kind, encounter_id, int(turn_revision), int(actor_id), encoded,
                normalized_target, RULES_VERSION, deadline_at, order_kind,
            ))
        if result.rowcount != 1:
            raise RuntimeError("combat_order_conflict")
        if owns:
            conn.commit()
        return {"accepted": True, "duplicate": False, "reason": "committed"}
    except Exception:
        if owns:
            conn.rollback()
        raise
    finally:
        if owns:
            conn.close()


def load_combat_orders(
    *, encounter_kind: str, encounter_id: str, turn_revision: int, conn=None,
) -> list[dict[str, Any]]:
    owns = conn is None
    if owns:
        conn = get_connection()
    try:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='combat_orders_v1'").fetchone():
            return []
        rows = conn.execute('''SELECT * FROM combat_orders_v1 WHERE encounter_kind=?
            AND encounter_id=? AND turn_revision=? ORDER BY created_at, actor_id''', (
                encounter_kind, encounter_id, int(turn_revision),
            )).fetchall()
        return [{**dict(row), "action": json.loads(str(row["action_json"]))} for row in rows]
    finally:
        if owns:
            conn.close()


def persist_turn_result(
    *,
    encounter_kind: str,
    encounter_id: str,
    turn_revision: int,
    result: dict[str, Any],
    complete_state: dict[str, Any],
    expected_previous_revision: int | None = None,
    conn=None,
) -> dict[str, Any]:
    """Persist an applied side exactly once and advance encounter authority."""
    owns = conn is None
    if owns:
        conn = get_connection()
        conn.execute("BEGIN IMMEDIATE")
    try:
        ensure_build_schema(conn)
        existing = conn.execute('''SELECT result_json, state_json FROM combat_turn_results_v1
            WHERE encounter_kind=? AND encounter_id=? AND turn_revision=?''', (
                encounter_kind, encounter_id, int(turn_revision),
            )).fetchone()
        if existing:
            if owns:
                conn.rollback()
            return {
                "applied": True,
                "duplicate": True,
                "result": json.loads(str(existing["result_json"])),
                "state": json.loads(str(existing["state_json"])),
            }
        table = "pve_encounters" if encounter_kind == "pve" else "pvp_engagements"
        id_column = "encounter_id" if encounter_kind == "pve" else "id"
        payload_column = ", battle_state_json" if encounter_kind == "pve" else ""
        revision_row = conn.execute(
            f"SELECT turn_revision, state_revision, rules_version{payload_column} FROM {table} WHERE {id_column}=?", (encounter_id,)
        ).fetchone()
        if not revision_row or str(revision_row["rules_version"]) != RULES_VERSION:
            if owns:
                conn.rollback()
            return {"applied": False, "reason": "encounter_rules_mismatch"}
        current_revision = int(revision_row["turn_revision"])
        current_state_revision = int(revision_row["state_revision"] or 0)
        expected_state_revision = int(complete_state.get("state_revision", current_state_revision) or 0)
        expected = current_revision if expected_previous_revision is None else int(expected_previous_revision)
        if (
            current_revision != expected or int(turn_revision) < current_revision
            or expected_state_revision != current_state_revision
        ):
            if owns:
                conn.rollback()
            return {"applied": False, "reason": "stale_revision"}
        complete_state["state_revision"] = current_state_revision + 1
        if encounter_kind == "pve":
            from game.regional_objectives import preserve_combat_credit_marker
            preserve_combat_credit_marker(
                json.loads(str(revision_row["battle_state_json"] or "{}")), complete_state,
            )
        conn.execute('''INSERT INTO combat_turn_results_v1
            (encounter_kind, encounter_id, turn_revision, result_json, state_json, rules_version)
            VALUES (?, ?, ?, ?, ?, ?)''', (
                encounter_kind, encounter_id, int(turn_revision), _stable_json(result),
                _stable_json(complete_state), RULES_VERSION,
            ))
        if encounter_kind == "pve":
            updated = conn.execute('''UPDATE pve_encounters SET battle_state_json=?, turn_revision=?,
                state_revision=state_revision+1, updated_at=CURRENT_TIMESTAMP
                WHERE encounter_id=? AND rules_version=? AND turn_revision=? AND state_revision=?''', (
                    _stable_json(complete_state), int(turn_revision), encounter_id, RULES_VERSION,
                    current_revision, current_state_revision,
                ))
        else:
            # PvP keeps its battle payload inside the established reason_context.
            updated = conn.execute('''UPDATE pvp_engagements SET reason_context=?, turn_revision=?,
                state_revision=state_revision+1, updated_at=CURRENT_TIMESTAMP
                WHERE id=? AND rules_version=? AND turn_revision=? AND state_revision=?''', (
                    _stable_json(complete_state), int(turn_revision), int(encounter_id), RULES_VERSION,
                    current_revision, current_state_revision,
                ))
        if updated.rowcount != 1:
            raise RuntimeError("combat_result_cas_conflict")
        if owns:
            conn.commit()
        return {"applied": True, "duplicate": False, "result": result, "state": complete_state}
    except Exception:
        if owns:
            conn.rollback()
        raise
    finally:
        if owns:
            conn.close()


def replay_turn_result(*, encounter_kind: str, encounter_id: str, turn_revision: int, conn=None) -> dict[str, Any] | None:
    owns = conn is None
    if owns:
        conn = get_connection()
    try:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='combat_turn_results_v1'").fetchone():
            return None
        row = conn.execute('''SELECT result_json, state_json FROM combat_turn_results_v1
            WHERE encounter_kind=? AND encounter_id=? AND turn_revision=?''', (
                encounter_kind, encounter_id, int(turn_revision),
            )).fetchone()
        return None if not row else {"result": json.loads(str(row["result_json"])), "state": json.loads(str(row["state_json"]))}
    finally:
        if owns:
            conn.close()
