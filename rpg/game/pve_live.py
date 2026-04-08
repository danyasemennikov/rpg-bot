from __future__ import annotations

from datetime import datetime, timezone

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


def runtime_encounter_id(player_id: int) -> str:
    return f'solo-pve-{int(player_id)}'


def enemy_participant_id(player_id: int) -> int:
    return -int(player_id)


def reset_solo_pve_runtime_store() -> None:
    _SOLO_PVE_RUNTIME_STORE.reset()


def clear_solo_pve_runtime(player_id: int) -> None:
    _SOLO_PVE_RUNTIME_STORE.remove(runtime_encounter_id(player_id))


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


def ensure_runtime_for_battle(*, player_id: int, battle_state: dict, now: datetime | None = None) -> EncounterRuntimeState:
    check_now = now or _utc_now()
    encounter_id = runtime_encounter_id(player_id)
    runtime_state = _SOLO_PVE_RUNTIME_STORE.get(encounter_id)
    if runtime_state is not None and battle_state.get('runtime_encounter_id') != encounter_id:
        _SOLO_PVE_RUNTIME_STORE.remove(encounter_id)
        runtime_state = None
    if runtime_state is None:
        runtime_state = _SOLO_PVE_RUNTIME.create_encounter(
            encounter_id=encounter_id,
            side_a_participants=[int(player_id)],
            side_b_participants=[enemy_participant_id(player_id)],
            active_side_id=SIDE_PLAYER,
        )
        runtime_state = _SOLO_PVE_RUNTIME.open_side_turn(encounter_id=encounter_id, now=check_now)
    elif runtime_state.side_turn_state == 'completed':
        runtime_state = _SOLO_PVE_RUNTIME.open_side_turn(encounter_id=encounter_id, now=check_now)

    sync_battle_projection_from_runtime(battle_state=battle_state, runtime_state=runtime_state)
    return runtime_state


def submit_player_commit(*, player_id: int, action_type: str, skill_id: str | None = None, item_id: str | None = None) -> tuple[bool, str]:
    encounter_id = runtime_encounter_id(player_id)
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
    encounter_id = runtime_encounter_id(player_id)
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
    encounter_id = runtime_encounter_id(player_id)
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
    encounter_id = runtime_encounter_id(player_id)
    runtime_state = _SOLO_PVE_RUNTIME.open_side_turn(
        encounter_id=encounter_id,
        now=_utc_now(),
        timeout_seconds=DEFAULT_SIDE_TURN_TIMEOUT_SECONDS,
    )
    sync_battle_projection_from_runtime(battle_state=battle_state, runtime_state=runtime_state)
    return runtime_state


def run_enemy_instant_side(*, player_id: int, battle_state: dict, on_enemy_action) -> None:
    encounter_id = runtime_encounter_id(player_id)
    runtime_state = _SOLO_PVE_RUNTIME.open_side_turn(encounter_id=encounter_id, now=_utc_now(), timeout_seconds=0)
    commit = _SOLO_PVE_RUNTIME.commit_action(
        encounter_id=encounter_id,
        participant_id=enemy_participant_id(player_id),
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
