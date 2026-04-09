from __future__ import annotations

import json
import uuid
import zlib
from datetime import datetime, timezone

from database import get_connection
from game.live_combat_runtime import (
    DEFAULT_SIDE_TURN_TIMEOUT_SECONDS,
    EncounterRuntimeState,
    LiveCombatRuntime,
    LiveCombatRuntimeStore,
)

SIDE_PLAYER = 'side_a'
SIDE_ENEMY = 'side_b'

_SOLO_PVE_RUNTIME_STORE = LiveCombatRuntimeStore()
_SOLO_PVE_RUNTIME = LiveCombatRuntime(_SOLO_PVE_RUNTIME_STORE)


def _ensure_pve_encounter_table() -> None:
    conn = get_connection()
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS pve_encounters (
            encounter_id      TEXT PRIMARY KEY,
            owner_player_id   INTEGER NOT NULL,
            status            TEXT NOT NULL,
            mob_id            TEXT,
            battle_state_json TEXT NOT NULL,
            mob_json          TEXT NOT NULL,
            created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            finished_at       TIMESTAMP
        )
        '''
    )
    conn.commit()
    conn.close()


def _serialize_payload(payload: dict | None) -> str:
    return json.dumps(payload or {}, ensure_ascii=False)


def _deserialize_payload(raw_payload: str | None) -> dict:
    if not raw_payload:
        return {}
    try:
        parsed = json.loads(raw_payload)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def create_solo_pve_encounter(*, player_id: int, battle_state: dict, mob: dict | None = None) -> str:
    _ensure_pve_encounter_table()
    encounter_id = f'pve-enc-{uuid.uuid4().hex[:12]}'
    conn = get_connection()
    conn.execute(
        '''
        UPDATE pve_encounters
        SET status='superseded', updated_at=CURRENT_TIMESTAMP, finished_at=CURRENT_TIMESTAMP
        WHERE owner_player_id=? AND status='active'
        ''',
        (player_id,),
    )
    conn.execute(
        '''
        INSERT INTO pve_encounters (
            encounter_id, owner_player_id, status, mob_id, battle_state_json, mob_json
        ) VALUES (?, ?, 'active', ?, ?, ?)
        ''',
        (
            encounter_id,
            player_id,
            str(battle_state.get('mob_id') or (mob or {}).get('id') or ''),
            _serialize_payload(battle_state),
            _serialize_payload(mob or {}),
        ),
    )
    conn.commit()
    conn.close()
    return encounter_id


def get_active_solo_pve_encounter_id(*, player_id: int) -> str | None:
    _ensure_pve_encounter_table()
    conn = get_connection()
    row = conn.execute(
        '''
        SELECT encounter_id
        FROM pve_encounters
        WHERE owner_player_id=? AND status='active'
        ORDER BY created_at DESC
        LIMIT 1
        ''',
        (player_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return str(row['encounter_id'])


def load_active_solo_pve_encounter(*, player_id: int) -> tuple[dict, dict] | None:
    _ensure_pve_encounter_table()
    conn = get_connection()
    row = conn.execute(
        '''
        SELECT battle_state_json, mob_json
        FROM pve_encounters
        WHERE owner_player_id=? AND status='active'
        ORDER BY created_at DESC
        LIMIT 1
        ''',
        (player_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return _deserialize_payload(row['battle_state_json']), _deserialize_payload(row['mob_json'])


def persist_solo_pve_encounter_state(*, encounter_id: str, battle_state: dict, mob: dict | None = None) -> None:
    if not encounter_id:
        return
    _ensure_pve_encounter_table()
    conn = get_connection()
    conn.execute(
        '''
        UPDATE pve_encounters
        SET battle_state_json=?, mob_json=?, mob_id=?, updated_at=CURRENT_TIMESTAMP
        WHERE encounter_id=? AND status='active'
        ''',
        (
            _serialize_payload(battle_state),
            _serialize_payload(mob or {}),
            str(battle_state.get('mob_id') or (mob or {}).get('id') or ''),
            encounter_id,
        ),
    )
    conn.commit()
    conn.close()


def finish_solo_pve_encounter(*, player_id: int, encounter_id: str | None = None, status: str = 'finished') -> None:
    _ensure_pve_encounter_table()
    resolved_encounter_id = encounter_id or get_active_solo_pve_encounter_id(player_id=player_id)
    if resolved_encounter_id:
        conn = get_connection()
        conn.execute(
            '''
            UPDATE pve_encounters
            SET status=?, updated_at=CURRENT_TIMESTAMP, finished_at=CURRENT_TIMESTAMP
            WHERE encounter_id=?
            ''',
            (status, resolved_encounter_id),
        )
        conn.commit()
        conn.close()
    clear_solo_pve_runtime(player_id=player_id, encounter_id=resolved_encounter_id)


def runtime_encounter_id(player_id: int, battle_state: dict | None = None) -> str | None:
    encounter_id = (battle_state or {}).get('pve_encounter_id')
    if encounter_id:
        return str(encounter_id)
    return get_active_solo_pve_encounter_id(player_id=player_id)


def enemy_participant_id(encounter_id: str) -> int:
    return -(zlib.crc32(encounter_id.encode('utf-8')) or 1)


def reset_solo_pve_runtime_store() -> None:
    _SOLO_PVE_RUNTIME_STORE.reset()


def clear_solo_pve_runtime(player_id: int, encounter_id: str | None = None) -> None:
    resolved_encounter_id = encounter_id or runtime_encounter_id(player_id)
    if not resolved_encounter_id:
        return
    _SOLO_PVE_RUNTIME_STORE.remove(resolved_encounter_id)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def sync_battle_projection_from_runtime(*, battle_state: dict, runtime_state: EncounterRuntimeState) -> None:
    battle_state['runtime_encounter_id'] = runtime_state.encounter_id
    battle_state['active_side'] = runtime_state.active_side_id
    battle_state['turn_revision'] = int(runtime_state.turn_revision)
    battle_state['side_turn_state'] = runtime_state.side_turn_state
    battle_state['side_deadline_at'] = _to_iso(runtime_state.side_deadline_at)
    battle_state['round_index'] = int(runtime_state.round_index)


def ensure_runtime_for_battle(
    *,
    player_id: int,
    battle_state: dict,
    mob: dict | None = None,
    now: datetime | None = None,
) -> EncounterRuntimeState:
    check_now = now or _utc_now()
    encounter_id = runtime_encounter_id(player_id, battle_state)
    if not encounter_id:
        encounter_id = create_solo_pve_encounter(player_id=player_id, battle_state=battle_state, mob=mob)
    battle_state['pve_encounter_id'] = encounter_id

    runtime_state = _SOLO_PVE_RUNTIME_STORE.get(encounter_id)
    if runtime_state is not None and battle_state.get('runtime_encounter_id') != encounter_id:
        _SOLO_PVE_RUNTIME_STORE.remove(encounter_id)
        runtime_state = None
    if runtime_state is None:
        runtime_state = _SOLO_PVE_RUNTIME.create_encounter(
            encounter_id=encounter_id,
            side_a_participants=[int(player_id)],
            side_b_participants=[enemy_participant_id(encounter_id)],
            active_side_id=SIDE_PLAYER,
        )
        runtime_state = _SOLO_PVE_RUNTIME.open_side_turn(encounter_id=encounter_id, now=check_now)
    elif runtime_state.side_turn_state == 'completed':
        runtime_state = _SOLO_PVE_RUNTIME.open_side_turn(encounter_id=encounter_id, now=check_now)

    sync_battle_projection_from_runtime(battle_state=battle_state, runtime_state=runtime_state)
    return runtime_state


def _resolve_encounter_id(*, player_id: int, battle_state: dict | None = None, encounter_id: str | None = None) -> str | None:
    return encounter_id or runtime_encounter_id(player_id, battle_state)


def submit_player_commit(
    *,
    player_id: int,
    action_type: str,
    skill_id: str | None = None,
    item_id: str | None = None,
    battle_state: dict | None = None,
    encounter_id: str | None = None,
) -> tuple[bool, str]:
    encounter_id = _resolve_encounter_id(player_id=player_id, battle_state=battle_state, encounter_id=encounter_id)
    if not encounter_id:
        return False, 'encounter_not_found'
    runtime_state = _SOLO_PVE_RUNTIME_STORE.get(encounter_id)
    if runtime_state is None:
        return False, 'encounter_not_found'

    commit_result = _SOLO_PVE_RUNTIME.commit_action(
        encounter_id=encounter_id,
        participant_id=int(player_id),
        action_type=action_type,
        target_info=None,
        skill_id=skill_id,
        item_id=item_id,
        committed_at=_utc_now(),
        turn_revision=runtime_state.turn_revision,
    )
    return commit_result.accepted, commit_result.reason


def _resolve_batch_by_action(*, batch, on_player_action, on_enemy_action) -> None:
    for action in batch:
        if action.participant_id > 0:
            on_player_action(action)
        else:
            on_enemy_action(action)


def resolve_current_side_if_ready(*, player_id: int, on_player_action, on_enemy_action) -> bool:
    encounter_id = _resolve_encounter_id(player_id=player_id)
    if not encounter_id:
        return False
    runtime_state = _SOLO_PVE_RUNTIME_STORE.get(encounter_id)
    if runtime_state is None:
        return False
    if runtime_state.side_turn_state != 'ready_to_lock':
        return False

    turn_revision = runtime_state.turn_revision
    claim = _SOLO_PVE_RUNTIME.claim_side_resolution(encounter_id=encounter_id, turn_revision=turn_revision)
    if not claim.claimed:
        return False

    batch = _SOLO_PVE_RUNTIME.build_resolution_batch(encounter_id=encounter_id)
    _resolve_batch_by_action(batch=batch, on_player_action=on_player_action, on_enemy_action=on_enemy_action)

    _SOLO_PVE_RUNTIME.complete_side_and_advance(encounter_id=encounter_id, turn_revision=turn_revision)
    return True


def resolve_due_player_timeout_if_any(*, player_id: int, now: datetime | None = None, on_player_action=None) -> bool:
    encounter_id = _resolve_encounter_id(player_id=player_id)
    if not encounter_id:
        return False
    runtime_state = _SOLO_PVE_RUNTIME_STORE.get(encounter_id)
    if runtime_state is None:
        return False

    assigned = _SOLO_PVE_RUNTIME.apply_timeout_fallbacks(encounter_id=encounter_id, now=now or _utc_now())
    if assigned <= 0:
        return False

    return resolve_current_side_if_ready(
        player_id=player_id,
        on_player_action=on_player_action or (lambda _action: None),
        on_enemy_action=lambda _action: None,
    )


def process_due_timeout_for_battle(
    *,
    player_id: int,
    battle_state: dict,
    on_player_timeout_action=None,
    on_enemy_action=None,
    now: datetime | None = None,
) -> bool:
    timed_out = resolve_due_player_timeout_if_any(
        player_id=player_id,
        now=now,
        on_player_action=on_player_timeout_action or (lambda _action: None),
    )
    if not timed_out:
        return False

    run_enemy_instant_side(
        player_id=player_id,
        battle_state=battle_state,
        on_enemy_action=on_enemy_action or (lambda _action: None),
    )
    return True


def open_next_player_side_turn(*, player_id: int, battle_state: dict) -> EncounterRuntimeState:
    encounter_id = _resolve_encounter_id(player_id=player_id, battle_state=battle_state)
    if not encounter_id:
        raise KeyError('Encounter not found for player side turn.')
    runtime_state = _SOLO_PVE_RUNTIME.open_side_turn(
        encounter_id=encounter_id,
        now=_utc_now(),
        timeout_seconds=DEFAULT_SIDE_TURN_TIMEOUT_SECONDS,
    )
    sync_battle_projection_from_runtime(battle_state=battle_state, runtime_state=runtime_state)
    return runtime_state


def run_enemy_instant_side(*, player_id: int, battle_state: dict, on_enemy_action) -> None:
    encounter_id = _resolve_encounter_id(player_id=player_id, battle_state=battle_state)
    if not encounter_id:
        return
    runtime_state = _SOLO_PVE_RUNTIME.open_side_turn(encounter_id=encounter_id, now=_utc_now(), timeout_seconds=0)
    commit = _SOLO_PVE_RUNTIME.commit_action(
        encounter_id=encounter_id,
        participant_id=enemy_participant_id(encounter_id),
        action_type='enemy_basic_attack',
        target_info=None,
        skill_id=None,
        item_id=None,
        committed_at=_utc_now(),
        turn_revision=runtime_state.turn_revision,
    )
    if not commit.accepted:
        sync_battle_projection_from_runtime(battle_state=battle_state, runtime_state=runtime_state)
        return

    resolved = resolve_current_side_if_ready(
        player_id=player_id,
        on_player_action=lambda _action: None,
        on_enemy_action=on_enemy_action,
    )
    if not resolved:
        sync_battle_projection_from_runtime(battle_state=battle_state, runtime_state=runtime_state)
        return

    runtime_state = open_next_player_side_turn(player_id=player_id, battle_state=battle_state)
    sync_battle_projection_from_runtime(battle_state=battle_state, runtime_state=runtime_state)
