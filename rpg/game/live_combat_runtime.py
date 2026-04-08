"""Unified live combat side-turn runtime foundation (phase 1).

This module is intentionally focused on orchestration/state contracts:
- two-side encounter runtime state
- side turn open/collect/lock/resolve/advance flow
- commit + timeout fallback behavior
- resolve-once race guard for callback/timeout collisions

It does not implement combat formulas or full skill semantics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Literal

DEFAULT_SIDE_TURN_TIMEOUT_SECONDS = 15

SideTurnState = Literal['collecting_orders', 'ready_to_lock', 'resolving', 'completed']
ParticipantPhaseState = Literal[
    'eligible',
    'committed',
    'auto_fallback',
    'unable_to_act',
    'defeated',
    'fled',
    'released',
]


@dataclass
class SubmittedAction:
    participant_id: int
    action_type: str
    target_info: dict | None
    skill_id: str | None
    item_id: str | None
    committed_at: datetime
    turn_revision: int
    source: Literal['commit', 'fallback']


@dataclass
class RuntimeParticipant:
    participant_id: int
    side_id: str
    phase_state: ParticipantPhaseState = 'eligible'


@dataclass
class RuntimeSide:
    side_id: str
    participant_order: list[int]


@dataclass
class EncounterRuntimeState:
    encounter_id: str
    sides: dict[str, RuntimeSide]
    participants: dict[int, RuntimeParticipant]
    active_side_id: str
    round_index: int = 1
    side_turn_state: SideTurnState = 'completed'
    side_deadline_at: datetime | None = None
    turn_revision: int = 0
    submitted_actions: dict[int, SubmittedAction] = field(default_factory=dict)
    resolving_revision: int | None = None
    last_claimed_revision: int | None = None


@dataclass(frozen=True)
class CommitResult:
    accepted: bool
    reason: str


@dataclass(frozen=True)
class ResolveClaimResult:
    claimed: bool
    reason: str


@dataclass(frozen=True)
class ParticipantPhaseResult:
    changed: bool
    reason: str


@dataclass(frozen=True)
class AdvanceResult:
    advanced: bool
    side_switched: bool
    new_active_side_id: str
    new_round_index: int


class LiveCombatRuntimeStore:
    """In-memory runtime store for phase 1 foundation.

    Important limitation: this process-local store is not durable across process
    restart and is not horizontally shared. It is intentionally minimal so that
    persistence adapters can be added in a follow-up PR.
    """

    def __init__(self):
        self._encounters: dict[str, EncounterRuntimeState] = {}
        self._lock = Lock()

    def save(self, state: EncounterRuntimeState) -> None:
        with self._lock:
            self._encounters[state.encounter_id] = state

    def get(self, encounter_id: str) -> EncounterRuntimeState | None:
        with self._lock:
            return self._encounters.get(encounter_id)

    def remove(self, encounter_id: str) -> None:
        with self._lock:
            self._encounters.pop(encounter_id, None)

    def reset(self) -> None:
        with self._lock:
            self._encounters.clear()


class LiveCombatRuntime:
    def __init__(self, store: LiveCombatRuntimeStore):
        self.store = store
        self._lock = Lock()

    def create_encounter(
        self,
        *,
        encounter_id: str,
        side_a_participants: list[int],
        side_b_participants: list[int],
        active_side_id: str = 'side_a',
    ) -> EncounterRuntimeState:
        if active_side_id not in ('side_a', 'side_b'):
            raise ValueError("active_side_id must be 'side_a' or 'side_b'.")
        if not side_a_participants or not side_b_participants:
            raise ValueError('Both sides must include at least one participant.')
        if len(set(side_a_participants)) != len(side_a_participants):
            raise ValueError('side_a_participants contains duplicate participant ids.')
        if len(set(side_b_participants)) != len(side_b_participants):
            raise ValueError('side_b_participants contains duplicate participant ids.')
        if set(side_a_participants) & set(side_b_participants):
            raise ValueError('Participants cannot belong to both side_a and side_b.')

        sides = {
            'side_a': RuntimeSide('side_a', list(side_a_participants)),
            'side_b': RuntimeSide('side_b', list(side_b_participants)),
        }
        participants: dict[int, RuntimeParticipant] = {}
        for pid in side_a_participants:
            participants[pid] = RuntimeParticipant(participant_id=pid, side_id='side_a')
        for pid in side_b_participants:
            participants[pid] = RuntimeParticipant(participant_id=pid, side_id='side_b')

        state = EncounterRuntimeState(
            encounter_id=encounter_id,
            sides=sides,
            participants=participants,
            active_side_id=active_side_id,
        )
        self.store.save(state)
        return state

    def open_side_turn(
        self,
        *,
        encounter_id: str,
        now: datetime | None = None,
        timeout_seconds: int = DEFAULT_SIDE_TURN_TIMEOUT_SECONDS,
    ) -> EncounterRuntimeState:
        check_now = now or datetime.now(timezone.utc)
        with self._lock:
            state = self._require_state(encounter_id)
            state.turn_revision += 1
            state.side_turn_state = 'collecting_orders'
            state.side_deadline_at = check_now + timedelta(seconds=timeout_seconds)
            state.submitted_actions = {}
            state.resolving_revision = None

            for participant in self._iter_active_side_participants(state):
                if participant.phase_state in ('defeated', 'fled', 'released'):
                    continue
                participant.phase_state = 'eligible'

            if self._is_active_side_fully_resolved_state(state):
                state.side_turn_state = 'ready_to_lock'

            return state

    def mark_participant_unable_to_act_for_current_phase(
        self,
        *,
        encounter_id: str,
        participant_id: int,
        turn_revision: int,
    ) -> ParticipantPhaseResult:
        """Mark participant as unable for the current side phase only."""
        with self._lock:
            state = self._require_state(encounter_id)
            if state.side_turn_state != 'collecting_orders':
                return ParticipantPhaseResult(False, 'turn_not_collecting')
            if turn_revision != state.turn_revision:
                return ParticipantPhaseResult(False, 'stale_revision')

            participant = state.participants.get(participant_id)
            if not participant:
                return ParticipantPhaseResult(False, 'participant_not_found')
            if participant.side_id != state.active_side_id:
                return ParticipantPhaseResult(False, 'wrong_side')
            if participant.phase_state in ('defeated', 'fled', 'released'):
                return ParticipantPhaseResult(False, 'participant_permanently_unavailable')
            if participant.phase_state in ('committed', 'auto_fallback'):
                return ParticipantPhaseResult(False, 'participant_already_resolved')

            participant.phase_state = 'unable_to_act'

            if self._is_active_side_fully_resolved_state(state):
                state.side_turn_state = 'ready_to_lock'
            return ParticipantPhaseResult(True, 'marked_unable_to_act')

    def get_active_side_eligible_participants(self, *, encounter_id: str) -> list[int]:
        state = self._require_state(encounter_id)
        return [
            p.participant_id
            for p in self._iter_active_side_participants(state)
            if p.phase_state == 'eligible'
        ]

    def commit_action(
        self,
        *,
        encounter_id: str,
        participant_id: int,
        action_type: str,
        target_info: dict | None,
        skill_id: str | None,
        item_id: str | None,
        committed_at: datetime | None,
        turn_revision: int,
    ) -> CommitResult:
        stamp = committed_at or datetime.now(timezone.utc)
        with self._lock:
            state = self._require_state(encounter_id)
            if state.side_turn_state != 'collecting_orders':
                return CommitResult(False, 'turn_not_collecting')
            if turn_revision != state.turn_revision:
                return CommitResult(False, 'stale_revision')

            participant = state.participants.get(participant_id)
            if not participant:
                return CommitResult(False, 'participant_not_found')
            if participant.side_id != state.active_side_id:
                return CommitResult(False, 'wrong_side')
            if participant.phase_state != 'eligible':
                return CommitResult(False, 'participant_not_eligible')

            action = SubmittedAction(
                participant_id=participant_id,
                action_type=action_type,
                target_info=target_info,
                skill_id=skill_id,
                item_id=item_id,
                committed_at=stamp,
                turn_revision=turn_revision,
                source='commit',
            )
            state.submitted_actions[participant_id] = action
            participant.phase_state = 'committed'

            if self._is_active_side_fully_resolved_state(state):
                state.side_turn_state = 'ready_to_lock'

            return CommitResult(True, 'committed')

    def apply_timeout_fallbacks(
        self,
        *,
        encounter_id: str,
        now: datetime | None = None,
    ) -> int:
        check_now = now or datetime.now(timezone.utc)
        with self._lock:
            state = self._require_state(encounter_id)
            if state.side_turn_state != 'collecting_orders':
                return 0
            if not state.side_deadline_at or check_now < state.side_deadline_at:
                return 0

            assigned = 0
            for participant in self._iter_active_side_participants(state):
                if participant.phase_state != 'eligible':
                    continue
                fallback = SubmittedAction(
                    participant_id=participant.participant_id,
                    action_type='fallback_guard',
                    target_info=None,
                    skill_id=None,
                    item_id=None,
                    committed_at=check_now,
                    turn_revision=state.turn_revision,
                    source='fallback',
                )
                state.submitted_actions[participant.participant_id] = fallback
                participant.phase_state = 'auto_fallback'
                assigned += 1

            if self._is_active_side_fully_resolved_state(state):
                state.side_turn_state = 'ready_to_lock'
            return assigned

    def is_active_side_fully_resolved(self, *, encounter_id: str) -> bool:
        state = self._require_state(encounter_id)
        return self._is_active_side_fully_resolved_state(state)

    def claim_side_resolution(
        self,
        *,
        encounter_id: str,
        turn_revision: int,
    ) -> ResolveClaimResult:
        """Resolve-once guard against callback/timeout races."""
        with self._lock:
            state = self._require_state(encounter_id)
            if turn_revision != state.turn_revision:
                return ResolveClaimResult(False, 'stale_revision')
            if state.side_turn_state not in ('ready_to_lock', 'resolving'):
                return ResolveClaimResult(False, 'side_not_lockable')
            if state.last_claimed_revision == turn_revision:
                return ResolveClaimResult(False, 'already_claimed')

            state.last_claimed_revision = turn_revision
            state.side_turn_state = 'resolving'
            state.resolving_revision = turn_revision
            return ResolveClaimResult(True, 'claimed')

    def build_resolution_batch(self, *, encounter_id: str) -> list[SubmittedAction]:
        state = self._require_state(encounter_id)
        ordered_ids = state.sides[state.active_side_id].participant_order
        return [
            state.submitted_actions[pid]
            for pid in ordered_ids
            if pid in state.submitted_actions
        ]

    def complete_side_and_advance(self, *, encounter_id: str, turn_revision: int) -> AdvanceResult:
        with self._lock:
            state = self._require_state(encounter_id)
            if turn_revision != state.turn_revision:
                return AdvanceResult(False, False, state.active_side_id, state.round_index)
            if state.resolving_revision != turn_revision:
                return AdvanceResult(False, False, state.active_side_id, state.round_index)

            previous_side = state.active_side_id
            state.side_turn_state = 'completed'
            state.side_deadline_at = None
            state.resolving_revision = None

            state.active_side_id = 'side_b' if previous_side == 'side_a' else 'side_a'
            if state.active_side_id == 'side_a':
                state.round_index += 1

            return AdvanceResult(
                advanced=True,
                side_switched=True,
                new_active_side_id=state.active_side_id,
                new_round_index=state.round_index,
            )

    def _require_state(self, encounter_id: str) -> EncounterRuntimeState:
        state = self.store.get(encounter_id)
        if not state:
            raise KeyError(f'Encounter not found: {encounter_id}')
        return state

    def _iter_active_side_participants(self, state: EncounterRuntimeState):
        for pid in state.sides[state.active_side_id].participant_order:
            participant = state.participants.get(pid)
            if participant:
                yield participant

    def _is_active_side_fully_resolved_state(self, state: EncounterRuntimeState) -> bool:
        unresolved_found = False
        for participant in self._iter_active_side_participants(state):
            if participant.phase_state in ('defeated', 'fled', 'released', 'unable_to_act'):
                continue
            if participant.phase_state in ('committed', 'auto_fallback'):
                continue
            unresolved_found = True
            break
        return not unresolved_found
