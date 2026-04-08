"""Live open-world 1v1 PvP flow helpers (phase: first playable slice)."""

from __future__ import annotations

import json
import random
from datetime import datetime, timezone

from database import get_connection
from game.balance import (
    calc_crit_chance,
    calc_defense_mitigation_percent,
    calc_final_damage,
    get_player_accuracy_rating,
    get_player_evasion_rating,
    normalize_damage_school,
    normalize_weapon_profile,
    apply_mitigation_percent,
    resolve_hit_check,
)
from game.equipment_stats import get_equipped_item_ids, get_player_effective_stats
from game.items_data import get_item
from game.i18n import get_player_lang, get_skill_name, t
from game.locations import get_location_security_tier
from game.pvp_death_policy import resolve_death_respawn_hub, resolve_pvp_death_loss_percent
from game.pvp_engagement import (
    ENGAGEMENT_STATE_CANCELLED,
    ENGAGEMENT_STATE_CONVERTED_TO_BATTLE,
    ENGAGEMENT_STATE_ESCAPED,
    ENGAGEMENT_STATE_PENDING,
    OpenWorldPvpEngagement,
    activate_engagement_if_ready,
    create_open_world_pvp_engagement,
    resolve_escape_attempt,
)
from game.pvp_inventory_policy import resolve_item_death_vulnerability
from game.pvp_rules import (
    RESPAWN_PROTECTION_WINDOW_SECONDS,
    count_recent_repeat_kills,
    resolve_illegal_aggression_infamy,
    resolve_kill_infamy_delta,
)
from game.pvp_turn_timing import ACTION_FAMILY_ATTACK, PvpActionOption, resolve_timed_turn_action
from game.skill_engine import get_battle_skills, precheck_skill_use, use_skill
from game.weapon_mastery import tick_cooldowns
from game.weapon_mastery import get_mastery

PVP_BATTLE_STATE_LIVE = 'live'
PVP_BATTLE_STATE_FINISHED = 'finished'
REPEAT_KILL_WINDOW_MINUTES = 30
ENGAGEMENT_BUSY_STATES = (ENGAGEMENT_STATE_PENDING, 'active', ENGAGEMENT_STATE_CONVERTED_TO_BATTLE)
REINFORCEMENT_STATUS_PENDING = 'pending'
REINFORCEMENT_STATUS_ACCEPTED = 'accepted'
REINFORCEMENT_STATUS_REJECTED = 'rejected'
REINFORCEMENT_STATUS_EXPIRED = 'expired'
REINFORCEMENT_SIDE_INITIATOR = 'initiator'
REINFORCEMENT_SIDE_DEFENDER = 'defender'
REINFORCEMENT_SIDES = (REINFORCEMENT_SIDE_INITIATOR, REINFORCEMENT_SIDE_DEFENDER)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _from_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _serialize_reason_context(payload: dict | None) -> str | None:
    if payload is None:
        return None
    return json.dumps(payload, ensure_ascii=False)


def _deserialize_reason_context(raw_value: str | None) -> dict:
    if not raw_value:
        return {}
    try:
        parsed = json.loads(raw_value)
    except (ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _ensure_reinforcement_table() -> None:
    conn = get_connection()
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS pvp_engagement_reinforcements (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            engagement_id INTEGER NOT NULL,
            side          TEXT NOT NULL,
            inviter_id    INTEGER NOT NULL,
            ally_id       INTEGER NOT NULL,
            status        TEXT NOT NULL,
            invited_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            responded_at  TIMESTAMP,
            FOREIGN KEY (engagement_id) REFERENCES pvp_engagements(id)
        )
        '''
    )
    conn.commit()
    conn.close()


def _is_player_busy_with_live_pvp_conn(conn, *, player_id: int) -> bool:
    row = conn.execute(
        '''
        SELECT id FROM pvp_engagements
        WHERE (attacker_id=? OR defender_id=?)
          AND engagement_state IN (?, ?, ?)
        LIMIT 1
        ''',
        (player_id, player_id, *ENGAGEMENT_BUSY_STATES),
    ).fetchone()
    reinforcement_row = conn.execute(
        '''
        SELECT pr.id
        FROM pvp_engagement_reinforcements pr
        JOIN pvp_engagements pe ON pe.id = pr.engagement_id
        WHERE pr.ally_id=?
          AND pr.status=?
          AND pe.engagement_state IN (?, ?)
        LIMIT 1
        ''',
        (player_id, REINFORCEMENT_STATUS_ACCEPTED, ENGAGEMENT_STATE_PENDING, 'active'),
    ).fetchone()
    return bool(row or reinforcement_row)


def _row_to_engagement(row) -> OpenWorldPvpEngagement:
    return OpenWorldPvpEngagement(
        attacker_id=int(row['attacker_id']),
        defender_id=int(row['defender_id']),
        location_id=str(row['location_id']),
        engagement_started_at=_from_iso(str(row['engagement_started_at'])),
        engagement_ready_at=_from_iso(str(row['engagement_ready_at'])),
        engagement_state=str(row['engagement_state']),
        reason_context=row['reason_context'],
        reinforcement_hook=row['reinforcement_hook'],
    )


def create_live_engagement(*, attacker: dict, defender: dict, location_id: str, illegal_aggression: bool) -> int:
    _ensure_reinforcement_table()
    engagement = create_open_world_pvp_engagement(
        attacker_id=int(attacker['telegram_id']),
        defender_id=int(defender['telegram_id']),
        location_id=location_id,
        reason_context='illegal_guarded_aggression' if illegal_aggression else 'open_world_attack',
        reinforcement_hook='future_reinforcement_slot',
    )
    payload = {
        'flow': 'open_world_1v1',
        'illegal_aggression': bool(illegal_aggression),
        'battle': None,
    }
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        '''
        INSERT INTO pvp_engagements (
            attacker_id, defender_id, location_id,
            engagement_started_at, engagement_ready_at,
            engagement_state, reason_context, reinforcement_hook
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            engagement.attacker_id,
            engagement.defender_id,
            engagement.location_id,
            _to_iso(engagement.engagement_started_at),
            _to_iso(engagement.engagement_ready_at),
            engagement.engagement_state,
            _serialize_reason_context(payload),
            engagement.reinforcement_hook,
        ),
    )
    engagement_id = int(cur.lastrowid)
    conn.commit()
    conn.close()
    return engagement_id


def can_create_live_engagement(*, attacker_id: int, defender_id: int) -> tuple[bool, str | None]:
    _ensure_reinforcement_table()
    conn = get_connection()
    attacker = conn.execute(
        'SELECT in_battle FROM players WHERE telegram_id=?',
        (attacker_id,),
    ).fetchone()
    defender = conn.execute(
        'SELECT in_battle FROM players WHERE telegram_id=?',
        (defender_id,),
    ).fetchone()
    if not attacker or not defender:
        conn.close()
        return False, 'missing_player'
    if int(attacker['in_battle'] or 0) == 1 or int(defender['in_battle'] or 0) == 1:
        conn.close()
        return False, 'already_in_battle'
    if _is_player_busy_with_live_pvp_conn(conn, player_id=attacker_id):
        conn.close()
        return False, 'attacker_busy'
    if _is_player_busy_with_live_pvp_conn(conn, player_id=defender_id):
        conn.close()
        return False, 'defender_busy'

    duplicate_pair = conn.execute(
        '''
        SELECT id FROM pvp_engagements
        WHERE attacker_id=? AND defender_id=?
          AND engagement_state IN (?, ?, ?)
        LIMIT 1
        ''',
        (attacker_id, defender_id, *ENGAGEMENT_BUSY_STATES),
    ).fetchone()
    conn.close()
    if duplicate_pair:
        return False, 'duplicate_pair'
    return True, None


def is_player_busy_with_live_pvp(player_id: int) -> bool:
    _ensure_reinforcement_table()
    conn = get_connection()
    is_busy = _is_player_busy_with_live_pvp_conn(conn, player_id=player_id)
    conn.close()
    return is_busy


def has_active_live_pvp_engagement(player_id: int) -> bool:
    """True when player is in pending/prep or converted live PvP engagement."""
    return is_player_busy_with_live_pvp(player_id)


def is_pvp_mobility_blocked(player_id: int) -> bool:
    """Movement/world-flow lock during any active live PvP engagement."""
    return has_active_live_pvp_engagement(player_id)


def get_pending_player_engagement(player_id: int):
    conn = get_connection()
    row = conn.execute(
        '''
        SELECT * FROM pvp_engagements
        WHERE (attacker_id=? OR defender_id=?)
          AND engagement_state IN (?, ?, ?)
        ORDER BY id DESC
        LIMIT 1
        ''',
        (player_id, player_id, ENGAGEMENT_STATE_PENDING, 'active', ENGAGEMENT_STATE_CONVERTED_TO_BATTLE),
    ).fetchone()
    conn.close()
    return row


def get_pending_reinforcement_engagement_for_player(player_id: int):
    """Return pending engagement row where player is invited or accepted ally."""
    _ensure_reinforcement_table()
    conn = get_connection()
    row = conn.execute(
        '''
        SELECT pe.*
        FROM pvp_engagements pe
        JOIN pvp_engagement_reinforcements pr ON pr.engagement_id = pe.id
        WHERE pr.ally_id=?
          AND pr.status IN (?, ?)
          AND pe.engagement_state=?
        ORDER BY pr.id DESC
        LIMIT 1
        ''',
        (
            player_id,
            REINFORCEMENT_STATUS_PENDING,
            REINFORCEMENT_STATUS_ACCEPTED,
            ENGAGEMENT_STATE_PENDING,
        ),
    ).fetchone()
    conn.close()
    return row


def _seconds_until_ready(engagement_row) -> int:
    ready_at = _from_iso(str(engagement_row['engagement_ready_at']))
    return max(0, int((ready_at - _utc_now()).total_seconds()))


def get_pending_location_encounters(*, location_id: str, limit: int = 3) -> list[dict]:
    _ensure_reinforcement_table()
    conn = get_connection()
    rows = conn.execute(
        '''
        SELECT pe.id, pe.attacker_id, pe.defender_id, pe.location_id, pe.engagement_ready_at, pe.engagement_state,
               a.name AS attacker_name, d.name AS defender_name
        FROM pvp_engagements pe
        JOIN players a ON a.telegram_id = pe.attacker_id
        JOIN players d ON d.telegram_id = pe.defender_id
        WHERE pe.location_id=? AND pe.engagement_state=?
        ORDER BY pe.id DESC
        LIMIT ?
        ''',
        (location_id, ENGAGEMENT_STATE_PENDING, max(1, int(limit))),
    ).fetchall()
    result: list[dict] = []
    for row in rows:
        joined_counts = conn.execute(
            '''
            SELECT side, COUNT(1) AS total
            FROM pvp_engagement_reinforcements
            WHERE engagement_id=? AND status=?
            GROUP BY side
            ''',
            (int(row['id']), REINFORCEMENT_STATUS_ACCEPTED),
        ).fetchall()
        side_counts = {REINFORCEMENT_SIDE_INITIATOR: 1, REINFORCEMENT_SIDE_DEFENDER: 1}
        for count_row in joined_counts:
            side = str(count_row['side'])
            if side in side_counts:
                side_counts[side] += int(count_row['total'] or 0)
        result.append({
            'id': int(row['id']),
            'location_id': str(row['location_id']),
            'attacker_id': int(row['attacker_id']),
            'defender_id': int(row['defender_id']),
            'attacker_name': row['attacker_name'] or f"#{int(row['attacker_id'])}",
            'defender_name': row['defender_name'] or f"#{int(row['defender_id'])}",
            'seconds_until_start': _seconds_until_ready(row),
            'initiator_side_count': side_counts[REINFORCEMENT_SIDE_INITIATOR],
            'defender_side_count': side_counts[REINFORCEMENT_SIDE_DEFENDER],
        })
    conn.close()
    return result


def get_pending_encounter_detail(*, engagement_id: int) -> dict | None:
    _ensure_reinforcement_table()
    conn = get_connection()
    row = conn.execute(
        '''
        SELECT pe.*, a.name AS attacker_name, d.name AS defender_name
        FROM pvp_engagements pe
        JOIN players a ON a.telegram_id = pe.attacker_id
        JOIN players d ON d.telegram_id = pe.defender_id
        WHERE pe.id=?
        ''',
        (engagement_id,),
    ).fetchone()
    if not row:
        conn.close()
        return None
    joined_rows = conn.execute(
        '''
        SELECT side, ally_id, p.name AS ally_name
        FROM pvp_engagement_reinforcements r
        LEFT JOIN players p ON p.telegram_id = r.ally_id
        WHERE r.engagement_id=? AND r.status=?
        ORDER BY r.id ASC
        ''',
        (engagement_id, REINFORCEMENT_STATUS_ACCEPTED),
    ).fetchall()
    conn.close()
    initiator_names = [row['attacker_name'] or f"#{int(row['attacker_id'])}"]
    defender_names = [row['defender_name'] or f"#{int(row['defender_id'])}"]
    for joined in joined_rows:
        name = joined['ally_name'] or f"#{int(joined['ally_id'])}"
        if str(joined['side']) == REINFORCEMENT_SIDE_INITIATOR:
            initiator_names.append(name)
        elif str(joined['side']) == REINFORCEMENT_SIDE_DEFENDER:
            defender_names.append(name)
    return {
        'id': int(row['id']),
        'location_id': str(row['location_id']),
        'engagement_state': str(row['engagement_state']),
        'attacker_id': int(row['attacker_id']),
        'defender_id': int(row['defender_id']),
        'attacker_name': row['attacker_name'] or f"#{int(row['attacker_id'])}",
        'defender_name': row['defender_name'] or f"#{int(row['defender_id'])}",
        'seconds_until_start': _seconds_until_ready(row),
        'initiator_names': initiator_names,
        'defender_names': defender_names,
    }


def _init_live_battle_payload(*, attacker_id: int, defender_id: int, now: datetime) -> dict:
    conn = get_connection()
    attacker_row = conn.execute('SELECT * FROM players WHERE telegram_id=?', (attacker_id,)).fetchone()
    defender_row = conn.execute('SELECT * FROM players WHERE telegram_id=?', (defender_id,)).fetchone()
    conn.close()
    attacker = dict(attacker_row) if attacker_row else {'max_hp': 100}
    defender = dict(defender_row) if defender_row else {'max_hp': 100}
    attacker_effective = get_player_effective_stats(attacker_id, attacker)
    defender_effective = get_player_effective_stats(defender_id, defender)
    return {
        'state': PVP_BATTLE_STATE_LIVE,
        'attacker_hp': max(1, min(int(attacker.get('hp', 1)), int(attacker_effective.get('max_hp', attacker.get('max_hp', 100))))),
        'defender_hp': max(1, min(int(defender.get('hp', 1)), int(defender_effective.get('max_hp', defender.get('max_hp', 100))))),
        'attacker_max_hp': int(attacker_effective.get('max_hp', attacker.get('max_hp', 100))),
        'defender_max_hp': int(defender_effective.get('max_hp', defender.get('max_hp', 100))),
        'attacker_mana': max(0, min(int(attacker.get('mana', 0)), int(attacker_effective.get('max_mana', attacker.get('max_mana', 0))))),
        'defender_mana': max(0, min(int(defender.get('mana', 0)), int(defender_effective.get('max_mana', defender.get('max_mana', 0))))),
        'attacker_max_mana': int(attacker_effective.get('max_mana', attacker.get('max_mana', 0))),
        'defender_max_mana': int(defender_effective.get('max_mana', defender.get('max_mana', 0))),
        'turn_owner': attacker_id,
        'turn_started_at': _to_iso(now),
        'guarded_player_id': None,
        'last_log': '',
    }


def _write_engagement_state(*, engagement_id: int, state: str, payload: dict) -> None:
    _ensure_reinforcement_table()
    conn = get_connection()
    conn.execute(
        '''
        UPDATE pvp_engagements
        SET engagement_state=?, reason_context=?, updated_at=CURRENT_TIMESTAMP
        WHERE id=?
        ''',
        (state, _serialize_reason_context(payload), engagement_id),
    )
    if state != ENGAGEMENT_STATE_PENDING:
        conn.execute(
            '''
            UPDATE pvp_engagement_reinforcements
            SET status=?, responded_at=CURRENT_TIMESTAMP
            WHERE engagement_id=? AND status IN (?, ?)
            ''',
            (
                REINFORCEMENT_STATUS_EXPIRED,
                engagement_id,
                REINFORCEMENT_STATUS_PENDING,
                REINFORCEMENT_STATUS_ACCEPTED,
            ),
        )
    conn.commit()
    conn.close()


def _resolve_side_for_player(*, engagement_row, player_id: int) -> str | None:
    if int(engagement_row['attacker_id']) == player_id:
        return REINFORCEMENT_SIDE_INITIATOR
    if int(engagement_row['defender_id']) == player_id:
        return REINFORCEMENT_SIDE_DEFENDER
    return None


def _is_reinforcement_eligibility_blocked(
    *,
    engagement_row,
    inviter_id: int,
    ally_id: int,
    allow_existing_side_slot: bool = False,
    allow_existing_ally_invite: bool = False,
) -> str | None:
    side = _resolve_side_for_player(engagement_row=engagement_row, player_id=inviter_id)
    if side is None:
        return 'not_participant'
    if int(ally_id) == int(inviter_id):
        return 'self_target'
    if int(ally_id) in {int(engagement_row['attacker_id']), int(engagement_row['defender_id'])}:
        return 'already_participant'
    if str(engagement_row['engagement_state']) != ENGAGEMENT_STATE_PENDING:
        return 'engagement_not_pending'
    if get_location_security_tier(str(engagement_row['location_id'])) == 'safe':
        return 'safe_zone'

    _ensure_reinforcement_table()
    conn = get_connection()
    inviter = conn.execute('SELECT telegram_id, location_id FROM players WHERE telegram_id=?', (inviter_id,)).fetchone()
    ally = conn.execute('SELECT telegram_id, location_id, in_battle FROM players WHERE telegram_id=?', (ally_id,)).fetchone()
    if not inviter or not ally:
        conn.close()
        return 'missing_player'
    if str(inviter['location_id']) != str(engagement_row['location_id']) or str(ally['location_id']) != str(engagement_row['location_id']):
        conn.close()
        return 'not_same_location'
    if int(ally['in_battle'] or 0) == 1:
        conn.close()
        return 'already_in_battle'
    if _is_player_busy_with_live_pvp_conn(conn, player_id=int(ally_id)):
        conn.close()
        return 'already_in_active_pvp'

    existing_ally_slot = conn.execute(
        '''
        SELECT pr.id
        FROM pvp_engagement_reinforcements pr
        JOIN pvp_engagements pe ON pe.id = pr.engagement_id
        WHERE pr.ally_id=?
          AND pr.status IN (?, ?)
          AND pe.engagement_state IN (?, ?, ?)
        LIMIT 1
        ''',
        (int(ally_id), REINFORCEMENT_STATUS_PENDING, REINFORCEMENT_STATUS_ACCEPTED, *ENGAGEMENT_BUSY_STATES),
    ).fetchone()
    conn.close()
    if existing_ally_slot and not allow_existing_ally_invite:
        return 'already_invited'
    return None


def can_join_pending_encounter_side(*, engagement_row, player_id: int, side: str) -> tuple[bool, str | None]:
    if side not in REINFORCEMENT_SIDES:
        return False, 'invalid_side'
    if str(engagement_row['engagement_state']) != ENGAGEMENT_STATE_PENDING:
        return False, 'engagement_not_pending'
    if get_location_security_tier(str(engagement_row['location_id'])) == 'safe':
        return False, 'safe_zone'
    if player_id in {int(engagement_row['attacker_id']), int(engagement_row['defender_id'])}:
        return False, 'already_participant'

    _ensure_reinforcement_table()
    conn = get_connection()
    player_row = conn.execute(
        'SELECT telegram_id, location_id, in_battle FROM players WHERE telegram_id=?',
        (player_id,),
    ).fetchone()
    if not player_row:
        conn.close()
        return False, 'missing_player'
    if str(player_row['location_id']) != str(engagement_row['location_id']):
        conn.close()
        return False, 'not_same_location'
    if int(player_row['in_battle'] or 0) == 1:
        conn.close()
        return False, 'already_in_battle'
    if _is_player_busy_with_live_pvp_conn(conn, player_id=player_id):
        conn.close()
        return False, 'already_in_active_pvp'
    already_joined = conn.execute(
        '''
        SELECT id
        FROM pvp_engagement_reinforcements
        WHERE engagement_id=? AND ally_id=? AND status IN (?, ?)
        LIMIT 1
        ''',
        (int(engagement_row['id']), player_id, REINFORCEMENT_STATUS_PENDING, REINFORCEMENT_STATUS_ACCEPTED),
    ).fetchone()
    conn.close()
    if already_joined:
        return False, 'already_joined'
    return True, None


def join_pending_encounter_side(*, engagement_row, player_id: int, side: str) -> tuple[bool, str | None]:
    ok, reason = can_join_pending_encounter_side(engagement_row=engagement_row, player_id=player_id, side=side)
    if not ok:
        return False, reason
    _ensure_reinforcement_table()
    conn = get_connection()
    conn.execute(
        '''
        INSERT INTO pvp_engagement_reinforcements (engagement_id, side, inviter_id, ally_id, status, responded_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''',
        (int(engagement_row['id']), side, int(player_id), int(player_id), REINFORCEMENT_STATUS_ACCEPTED),
    )
    conn.commit()
    conn.close()
    return True, None


def invite_reinforcement_ally(*, engagement_row, inviter_id: int, ally_id: int) -> tuple[bool, str | None]:
    reason = _is_reinforcement_eligibility_blocked(
        engagement_row=engagement_row,
        inviter_id=inviter_id,
        ally_id=ally_id,
    )
    if reason is not None:
        return False, reason
    side = _resolve_side_for_player(engagement_row=engagement_row, player_id=inviter_id)
    _ensure_reinforcement_table()
    conn = get_connection()
    conn.execute(
        '''
        INSERT INTO pvp_engagement_reinforcements (engagement_id, side, inviter_id, ally_id, status)
        VALUES (?, ?, ?, ?, ?)
        ''',
        (int(engagement_row['id']), side, int(inviter_id), int(ally_id), REINFORCEMENT_STATUS_PENDING),
    )
    conn.commit()
    conn.close()
    return True, None


def respond_to_reinforcement_invite(*, engagement_id: int, ally_id: int, accepted: bool) -> tuple[bool, str | None]:
    _ensure_reinforcement_table()
    conn = get_connection()
    engagement_row = conn.execute('SELECT * FROM pvp_engagements WHERE id=?', (engagement_id,)).fetchone()
    invite_row = conn.execute(
        '''
        SELECT * FROM pvp_engagement_reinforcements
        WHERE engagement_id=? AND ally_id=? AND status=?
        ORDER BY id DESC
        LIMIT 1
        ''',
        (engagement_id, ally_id, REINFORCEMENT_STATUS_PENDING),
    ).fetchone()
    if not engagement_row or not invite_row:
        conn.close()
        return False, 'invite_missing'
    if str(engagement_row['engagement_state']) != ENGAGEMENT_STATE_PENDING:
        conn.execute(
            'UPDATE pvp_engagement_reinforcements SET status=?, responded_at=CURRENT_TIMESTAMP WHERE id=?',
            (REINFORCEMENT_STATUS_EXPIRED, int(invite_row['id'])),
        )
        conn.commit()
        conn.close()
        return False, 'engagement_not_pending'
    if not accepted:
        conn.execute(
            'UPDATE pvp_engagement_reinforcements SET status=?, responded_at=CURRENT_TIMESTAMP WHERE id=?',
            (REINFORCEMENT_STATUS_REJECTED, int(invite_row['id'])),
        )
        conn.commit()
        conn.close()
        return True, None

    block_reason = _is_reinforcement_eligibility_blocked(
        engagement_row=engagement_row,
        inviter_id=int(invite_row['inviter_id']),
        ally_id=int(ally_id),
        allow_existing_side_slot=True,
        allow_existing_ally_invite=True,
    )
    if block_reason is not None:
        conn.execute(
            'UPDATE pvp_engagement_reinforcements SET status=?, responded_at=CURRENT_TIMESTAMP WHERE id=?',
            (REINFORCEMENT_STATUS_REJECTED, int(invite_row['id'])),
        )
        conn.commit()
        conn.close()
        return False, block_reason
    conn.execute(
        'UPDATE pvp_engagement_reinforcements SET status=?, responded_at=CURRENT_TIMESTAMP WHERE id=?',
        (REINFORCEMENT_STATUS_ACCEPTED, int(invite_row['id'])),
    )
    conn.commit()
    conn.close()
    return True, None


def get_engagement_reinforcement_state(*, engagement_id: int) -> dict:
    _ensure_reinforcement_table()
    conn = get_connection()
    rows = conn.execute(
        '''
        SELECT pr.*, p.name AS ally_name
        FROM pvp_engagement_reinforcements pr
        LEFT JOIN players p ON p.telegram_id = pr.ally_id
        WHERE pr.engagement_id=?
        ORDER BY pr.id DESC
        ''',
        (engagement_id,),
    ).fetchall()
    conn.close()
    state: dict[str, dict] = {REINFORCEMENT_SIDE_INITIATOR: {}, REINFORCEMENT_SIDE_DEFENDER: {}}
    for row in rows:
        side = str(row['side'])
        if side not in state or state[side]:
            continue
        state[side] = {
            'status': str(row['status']),
            'ally_id': int(row['ally_id']),
            'ally_name': row['ally_name'] or f"#{int(row['ally_id'])}",
        }
    return state


def get_pending_reinforcement_invite_for_player(*, engagement_id: int, ally_id: int):
    _ensure_reinforcement_table()
    conn = get_connection()
    row = conn.execute(
        '''
        SELECT *
        FROM pvp_engagement_reinforcements
        WHERE engagement_id=? AND ally_id=? AND status=?
        ORDER BY id DESC
        LIMIT 1
        ''',
        (engagement_id, ally_id, REINFORCEMENT_STATUS_PENDING),
    ).fetchone()
    conn.close()
    return row


def is_player_joined_pending_encounter(*, engagement_id: int, player_id: int) -> bool:
    _ensure_reinforcement_table()
    conn = get_connection()
    row = conn.execute(
        '''
        SELECT id
        FROM pvp_engagement_reinforcements
        WHERE engagement_id=? AND ally_id=? AND status=?
        LIMIT 1
        ''',
        (engagement_id, player_id, REINFORCEMENT_STATUS_ACCEPTED),
    ).fetchone()
    conn.close()
    return bool(row)


def list_reinforcement_candidates(*, engagement_row, inviter_id: int, limit: int = 3) -> list[dict]:
    side = _resolve_side_for_player(engagement_row=engagement_row, player_id=inviter_id)
    if side is None or str(engagement_row['engagement_state']) != ENGAGEMENT_STATE_PENDING:
        return []
    _ensure_reinforcement_table()
    conn = get_connection()
    rows = conn.execute(
        '''
        SELECT telegram_id, name, level, location_id, in_battle
        FROM players
        WHERE location_id=? AND telegram_id NOT IN (?, ?)
        ORDER BY level DESC, telegram_id ASC
        LIMIT 20
        ''',
        (str(engagement_row['location_id']), int(engagement_row['attacker_id']), int(engagement_row['defender_id'])),
    ).fetchall()
    conn.close()
    result: list[dict] = []
    for row in rows:
        ally_id = int(row['telegram_id'])
        reason = _is_reinforcement_eligibility_blocked(
            engagement_row=engagement_row,
            inviter_id=inviter_id,
            ally_id=ally_id,
        )
        if reason is not None:
            continue
        result.append(dict(row))
        if len(result) >= limit:
            break
    return result


def advance_engagement_to_live_battle_if_ready(engagement_row, *, now: datetime | None = None) -> tuple[str, dict]:
    if not engagement_row:
        return 'missing', {}
    check_now = now or _utc_now()
    engagement = _row_to_engagement(engagement_row)
    payload = _deserialize_reason_context(engagement_row['reason_context'])
    updated = activate_engagement_if_ready(engagement, now=check_now)
    if updated.engagement_state != 'active':
        return engagement.engagement_state, payload
    payload['battle'] = _init_live_battle_payload(
        attacker_id=engagement.attacker_id,
        defender_id=engagement.defender_id,
        now=check_now,
    )
    _write_engagement_state(
        engagement_id=int(engagement_row['id']),
        state=ENGAGEMENT_STATE_CONVERTED_TO_BATTLE,
        payload=payload,
    )
    conn = get_connection()
    conn.execute(
        'UPDATE players SET in_battle=1 WHERE telegram_id IN (?, ?)',
        (engagement.attacker_id, engagement.defender_id),
    )
    conn.commit()
    conn.close()
    return ENGAGEMENT_STATE_CONVERTED_TO_BATTLE, payload


def resolve_engagement_escape(engagement_row, *, escape_succeeded: bool) -> tuple[str, bool]:
    if not engagement_row:
        return 'missing', False
    engagement = _row_to_engagement(engagement_row)
    payload = _deserialize_reason_context(engagement_row['reason_context'])
    updated, should_start_battle = resolve_escape_attempt(
        engagement,
        escape_succeeded=escape_succeeded,
    )
    if should_start_battle:
        payload['battle'] = _init_live_battle_payload(
            attacker_id=engagement.attacker_id,
            defender_id=engagement.defender_id,
            now=_utc_now(),
        )
    _write_engagement_state(
        engagement_id=int(engagement_row['id']),
        state=updated.engagement_state,
        payload=payload,
    )
    if updated.engagement_state == ENGAGEMENT_STATE_ESCAPED:
        conn = get_connection()
        conn.execute(
            'UPDATE players SET in_battle=0 WHERE telegram_id IN (?, ?)',
            (engagement.attacker_id, engagement.defender_id),
        )
        conn.commit()
        conn.close()
    if should_start_battle:
        conn = get_connection()
        conn.execute(
            'UPDATE players SET in_battle=1 WHERE telegram_id IN (?, ?)',
            (engagement.attacker_id, engagement.defender_id),
        )
        conn.commit()
        conn.close()
    return updated.engagement_state, should_start_battle


def _get_action_options() -> list[PvpActionOption]:
    return [PvpActionOption('normal_attack', ACTION_FAMILY_ATTACK, True), PvpActionOption('guard', 'defensive', True)]


def _build_player_skill_actions(player_id: int, weapon_id: str, mastery_level: int, weapon_profile: str) -> list[str]:
    allowed_skill_ids = {
        'power_strike',
        'quick_shot',
        'fireball',
        'ice_spike',
        'holy_bolt',
        'smite',
        'poison_stab',
    }
    actions: list[str] = []
    for skill in get_battle_skills(player_id, weapon_id, mastery_level, weapon_profile):
        if skill['id'] not in allowed_skill_ids:
            continue
        actions.append(f"skill:{skill['id']}")
    return actions


def _is_live_skill_action_ready(*, skill_id: str, actor_id: int, actor_mana: int, lang: str) -> bool:
    return precheck_skill_use(skill_id, actor_mana, actor_id, lang).get('success', False)


def get_manual_pvp_action_labels(
    *,
    player_id: int,
    lang: str,
    battle: dict | None = None,
    attacker_id: int | None = None,
    defender_id: int | None = None,
) -> list[tuple[str, str]]:
    conn = get_connection()
    row = conn.execute('SELECT * FROM players WHERE telegram_id=?', (player_id,)).fetchone()
    conn.close()
    if not row:
        return []
    player_row = dict(row)
    profile = _resolve_combat_profile(player_id, player_row)
    current_mana = int(player_row.get('mana', 0))
    if battle:
        if attacker_id is not None and player_id == int(attacker_id):
            current_mana = int(battle.get('attacker_mana', current_mana))
        elif defender_id is not None and player_id == int(defender_id):
            current_mana = int(battle.get('defender_mana', current_mana))
    labels = [('normal_attack', t('location.pvp_action_attack_btn', lang)), ('guard', t('location.pvp_action_guard_btn', lang))]
    for action in _build_player_skill_actions(
        player_id,
        profile['weapon_id'],
        profile['mastery_level'],
        profile['weapon_profile'],
    ):
        skill_id = action.replace('skill:', '', 1)
        if not _is_live_skill_action_ready(skill_id=skill_id, actor_id=player_id, actor_mana=current_mana, lang=lang):
            continue
        labels.append((action, f"🔮 {get_skill_name(skill_id, lang)}"))
    return labels


def _build_turn_action_options(
    *,
    actor_id: int,
    battle: dict,
    actor_profile: dict,
    is_attacker_side: bool,
    lang: str,
) -> list[PvpActionOption]:
    actor_hp = int(battle.get('attacker_hp' if is_attacker_side else 'defender_hp', 1))
    actor_max_hp = int(battle.get('attacker_max_hp' if is_attacker_side else 'defender_max_hp', max(1, actor_hp)))
    actor_mana = int(battle.get('attacker_mana' if is_attacker_side else 'defender_mana', 0))
    guard_ready = actor_hp <= max(1, int(actor_max_hp * 0.45))

    options = [
        PvpActionOption('normal_attack', ACTION_FAMILY_ATTACK, True),
        PvpActionOption('guard', 'defensive', guard_ready),
    ]
    for skill_action in _build_player_skill_actions(
        actor_id,
        actor_profile['weapon_id'],
        actor_profile['mastery_level'],
        actor_profile['weapon_profile'],
    ):
        skill_id = skill_action.replace('skill:', '', 1)
        skill_ready = _is_live_skill_action_ready(skill_id=skill_id, actor_id=actor_id, actor_mana=actor_mana, lang=lang)
        options.append(PvpActionOption(skill_action, 'core', skill_ready))
    return options


def _resolve_combat_profile(player_id: int, player_row: dict) -> dict:
    effective = get_player_effective_stats(player_id, player_row)
    equipped_item_ids = get_equipped_item_ids(player_id)
    weapon_id = equipped_item_ids.get('weapon', 'unarmed')
    weapon = get_item(weapon_id) or {}
    weapon_type = weapon.get('weapon_type', 'melee')
    weapon_profile = normalize_weapon_profile(weapon.get('weapon_profile'), weapon_type)
    damage_school = normalize_damage_school(weapon.get('damage_school'), weapon_profile=weapon_profile, weapon_type=weapon_type)
    mastery = get_mastery(player_id, weapon_id if weapon_id else 'unarmed')
    return {
        'weapon_id': weapon_id,
        'weapon': weapon,
        'weapon_type': weapon_type,
        'weapon_profile': weapon_profile,
        'damage_school': damage_school,
        'effective': effective,
        'mastery_level': int(mastery.get('level', 1)),
    }


def _resolve_normal_attack_damage(*, attacker_id: int, defender_id: int, defended_target: bool) -> tuple[int, bool, bool]:
    conn = get_connection()
    attacker_row = conn.execute('SELECT * FROM players WHERE telegram_id=?', (attacker_id,)).fetchone()
    defender_row = conn.execute('SELECT * FROM players WHERE telegram_id=?', (defender_id,)).fetchone()
    conn.close()
    if not attacker_row or not defender_row:
        return 0, False, False

    attacker = _resolve_combat_profile(attacker_id, dict(attacker_row))
    defender = _resolve_combat_profile(defender_id, dict(defender_row))
    hit_check = resolve_hit_check(
        get_player_accuracy_rating(attacker['effective'], {'mastery_level': attacker['mastery_level']}),
        get_player_evasion_rating(defender['effective'], {}),
    )
    if not hit_check['is_hit']:
        return 0, False, False

    is_crit = random.random() < calc_crit_chance(
        int(attacker['effective'].get('luck', 1)),
        int(attacker['effective'].get('agility', 1)),
    )
    weapon = attacker['weapon']
    base_weapon_damage = random.randint(
        int(weapon.get('damage_min', 8)),
        int(weapon.get('damage_max', 12)),
    )
    outgoing = calc_final_damage(
        base_weapon_damage=base_weapon_damage,
        attacker_stats=attacker['effective'],
        weapon_type=attacker['weapon_type'],
        is_crit=is_crit,
        weapon_profile=attacker['weapon_profile'],
        damage_school=attacker['damage_school'],
    )
    defense_rating = int(defender['effective'].get('effective_magic_defense', 0))
    if attacker['damage_school'] == 'physical':
        defense_rating = int(defender['effective'].get('effective_physical_defense', 0))
    mitigated = apply_mitigation_percent(
        outgoing,
        calc_defense_mitigation_percent(defense_rating, school=attacker['damage_school']),
    )
    if defended_target:
        mitigated = max(1, int(mitigated * 0.60))
    return mitigated, is_crit, True


def _resolve_skill_action(
    *,
    actor_id: int,
    target_id: int,
    action_id: str,
    battle: dict,
    is_attacker_side: bool,
) -> tuple[int, int, str]:
    skill_id = action_id.replace('skill:', '', 1)
    conn = get_connection()
    actor_row = conn.execute('SELECT * FROM players WHERE telegram_id=?', (actor_id,)).fetchone()
    target_row = conn.execute('SELECT * FROM players WHERE telegram_id=?', (target_id,)).fetchone()
    conn.close()
    if not actor_row or not target_row:
        return 0, int(battle.get('attacker_mana' if is_attacker_side else 'defender_mana', 0)), f'skill_fail:{skill_id}'
    actor_profile = _resolve_combat_profile(actor_id, dict(actor_row))
    target_profile = _resolve_combat_profile(target_id, dict(target_row))

    actor_hp_key = 'attacker_hp' if is_attacker_side else 'defender_hp'
    target_hp_key = 'defender_hp' if is_attacker_side else 'attacker_hp'
    actor_mana_key = 'attacker_mana' if is_attacker_side else 'defender_mana'
    current_mana = int(battle.get(actor_mana_key, 0))
    lang = get_player_lang(actor_id)
    if not _is_live_skill_action_ready(skill_id=skill_id, actor_id=actor_id, actor_mana=current_mana, lang=lang):
        return 0, current_mana, f'skill_fail:{skill_id}'

    player_runtime = {
        'id': actor_id,
        'telegram_id': actor_id,
        'strength': int(actor_profile['effective'].get('strength', 1)),
        'agility': int(actor_profile['effective'].get('agility', 1)),
        'intuition': int(actor_profile['effective'].get('intuition', 1)),
        'vitality': int(actor_profile['effective'].get('vitality', 1)),
        'wisdom': int(actor_profile['effective'].get('wisdom', 1)),
        'luck': int(actor_profile['effective'].get('luck', 1)),
        'weapon_type': actor_profile['weapon_type'],
        'weapon_profile': actor_profile['weapon_profile'],
        'damage_school': actor_profile['damage_school'],
        'weapon_damage': random.randint(
            int(actor_profile['weapon'].get('damage_min', 8)),
            int(actor_profile['weapon'].get('damage_max', 12)),
        ),
        'hp': int(battle.get(actor_hp_key, 1)),
        'max_hp': int(battle.get('attacker_max_hp' if is_attacker_side else 'defender_max_hp', 1)),
        'mana': current_mana,
        'max_mana': int(actor_profile['effective'].get('max_mana', 0)),
        'armor_class': 'medium',
        'offhand_profile': 'none',
        'encumbrance': 0,
    }
    mob_state = {
        'hp': int(battle.get(target_hp_key, 1)),
        'defense': int(target_profile['effective'].get('effective_physical_defense', 0)),
        'effects': [],
    }
    runtime_battle_state = {
        'player_mana': current_mana,
        'player_max_mana': int(actor_profile['effective'].get('max_mana', 0)),
        'mob_effects': [],
        'weapon_profile': actor_profile['weapon_profile'],
        'damage_school': actor_profile['damage_school'],
        'equipment_magic_power_bonus': int(actor_profile['effective'].get('magic_power_bonus', 0)),
        'equipment_healing_power_bonus': int(actor_profile['effective'].get('healing_power_bonus', 0)),
        'equipment_accuracy_bonus': int(actor_profile['effective'].get('accuracy_bonus', 0)),
        'equipment_evasion_bonus': int(actor_profile['effective'].get('evasion_bonus', 0)),
    }
    skill_result = use_skill(skill_id, player_runtime, mob_state, runtime_battle_state, actor_id, lang)
    if not skill_result.get('success'):
        return 0, current_mana, f'skill_fail:{skill_id}'
    target_damage = max(0, int(battle.get(target_hp_key, 1)) - int(mob_state.get('hp', 1)))
    next_mana = int(runtime_battle_state.get('player_mana', current_mana))
    return target_damage, next_mana, f'skill_ok:{skill_id}'


def resolve_live_battle_turn(engagement_row, *, actor_id: int, selected_action_id: str | None) -> tuple[str, dict]:
    payload = _deserialize_reason_context(engagement_row['reason_context'])
    battle = payload.get('battle') or {}
    if battle.get('state') != PVP_BATTLE_STATE_LIVE:
        return 'not_live', payload

    turn_owner = int(battle.get('turn_owner', 0))
    if actor_id != turn_owner:
        return 'not_your_turn', payload

    turn_started_at = _from_iso(battle['turn_started_at'])
    attacker_id = int(engagement_row['attacker_id'])
    defender_id = int(engagement_row['defender_id'])
    conn = get_connection()
    actor_row = conn.execute('SELECT * FROM players WHERE telegram_id=?', (actor_id,)).fetchone()
    conn.close()
    if not actor_row:
        return 'not_live', payload
    actor_profile = _resolve_combat_profile(actor_id, dict(actor_row))
    lang = get_player_lang(actor_id)
    available_options = _build_turn_action_options(
        actor_id=actor_id,
        battle=battle,
        actor_profile=actor_profile,
        is_attacker_side=(actor_id == attacker_id),
        lang=lang,
    )
    if selected_action_id:
        selected_ready = any(
            option.action_id == selected_action_id and option.is_ready
            for option in available_options
        )
        if not selected_ready:
            return 'invalid_action', payload
    resolution = resolve_timed_turn_action(
        turn_started_at=turn_started_at,
        available_options=available_options,
        selected_action_id=selected_action_id,
    )
    if resolution is None:
        return 'waiting', payload

    target_id = defender_id if actor_id == attacker_id else attacker_id
    is_attacker_side = actor_id == attacker_id
    actor_mana_key = 'attacker_mana' if is_attacker_side else 'defender_mana'
    target_guarded = battle.get('guarded_player_id') == target_id
    damage = 0
    is_crit = False
    did_hit = True
    if resolution.action_id == 'guard':
        battle['guarded_player_id'] = actor_id
        battle['last_log'] = f'{actor_id}:{resolution.action_source}:guard:0'
    elif resolution.action_id.startswith('skill:'):
        skill_damage, next_mana, log_tag = _resolve_skill_action(
            actor_id=actor_id,
            target_id=target_id,
            action_id=resolution.action_id,
            battle=battle,
            is_attacker_side=is_attacker_side,
        )
        if log_tag.startswith('skill_fail'):
            return 'invalid_action', payload
        battle[actor_mana_key] = max(0, next_mana)
        if actor_id == attacker_id:
            battle['defender_hp'] = max(0, int(battle.get('defender_hp', 1)) - skill_damage)
        else:
            battle['attacker_hp'] = max(0, int(battle.get('attacker_hp', 1)) - skill_damage)
        battle['guarded_player_id'] = None
        battle['last_log'] = f'{actor_id}:{resolution.action_source}:{log_tag}:{skill_damage}'
    else:
        damage, is_crit, did_hit = _resolve_normal_attack_damage(
            attacker_id=actor_id,
            defender_id=target_id,
            defended_target=target_guarded,
        )
        if actor_id == attacker_id:
            battle['defender_hp'] = max(0, int(battle.get('defender_hp', 1)) - damage)
        else:
            battle['attacker_hp'] = max(0, int(battle.get('attacker_hp', 1)) - damage)
        battle['guarded_player_id'] = None
        battle['last_log'] = f'{actor_id}:{resolution.action_source}:{resolution.action_id}:{damage}:{int(is_crit)}:{int(did_hit)}'

    battle['turn_owner'] = target_id
    battle['turn_started_at'] = _to_iso(_utc_now())
    tick_cooldowns(actor_id)

    winner_id = None
    loser_id = None
    if battle['attacker_hp'] <= 0:
        winner_id = defender_id
        loser_id = attacker_id
    elif battle['defender_hp'] <= 0:
        winner_id = attacker_id
        loser_id = defender_id

    payload['battle'] = battle
    if winner_id and loser_id:
        _finalize_pvp_battle(
            engagement_row=engagement_row,
            payload=payload,
            winner_id=winner_id,
            loser_id=loser_id,
        )
        return 'finished', payload

    _write_engagement_state(
        engagement_id=int(engagement_row['id']),
        state=ENGAGEMENT_STATE_CONVERTED_TO_BATTLE,
        payload=payload,
    )
    return 'resolved', payload


def _resolve_repeat_kill_dampening(*, winner_id: int, loser_id: int) -> tuple[int, float]:
    recent_kills = count_recent_repeat_kills(
        winner_id=winner_id,
        loser_id=loser_id,
        window_minutes=REPEAT_KILL_WINDOW_MINUTES,
    )
    if recent_kills <= 0:
        return 0, 1.0
    if recent_kills == 1:
        return recent_kills, 0.50
    return recent_kills, 0.25


def _transfer_vulnerable_inventory(*, winner_id: int, loser_id: int, location_id: str, transfer_scale: float = 1.0) -> None:
    loss_percent = resolve_pvp_death_loss_percent(location_id=location_id)
    if loss_percent <= 0:
        return
    scaled_loss_percent = max(0.0, min(1.0, loss_percent * transfer_scale))
    if scaled_loss_percent <= 0:
        return

    conn = get_connection()
    rows = conn.execute(
        '''
        SELECT item_id, quantity
        FROM inventory
        WHERE telegram_id=? AND quantity > 0
        ''',
        (loser_id,),
    ).fetchall()
    for row in rows:
        vulnerability = resolve_item_death_vulnerability(str(row['item_id']))
        if not vulnerability.vulnerable_on_pvp_death:
            continue
        total_quantity = int(row['quantity'])
        lost_quantity = int(total_quantity * scaled_loss_percent)
        if lost_quantity <= 0:
            continue
        conn.execute(
            '''
            UPDATE inventory
            SET quantity = quantity - ?
            WHERE telegram_id=? AND item_id=?
            ''',
            (lost_quantity, loser_id, row['item_id']),
        )
        existing = conn.execute(
            'SELECT id, quantity FROM inventory WHERE telegram_id=? AND item_id=?',
            (winner_id, row['item_id']),
        ).fetchone()
        if existing:
            conn.execute(
                'UPDATE inventory SET quantity=quantity+? WHERE id=?',
                (lost_quantity, existing['id']),
            )
        else:
            conn.execute(
                'INSERT INTO inventory (telegram_id, item_id, quantity) VALUES (?, ?, ?)',
                (winner_id, row['item_id'], lost_quantity),
            )
    conn.execute(
        'DELETE FROM inventory WHERE telegram_id=? AND quantity<=0',
        (loser_id,),
    )
    conn.commit()
    conn.close()


def _apply_pvp_defeat(*, loser_id: int, location_id: str) -> None:
    conn = get_connection()
    loser = conn.execute('SELECT max_hp FROM players WHERE telegram_id=?', (loser_id,)).fetchone()
    max_hp = int(loser['max_hp']) if loser else 100
    respawn_hub = resolve_death_respawn_hub(location_id=location_id)
    conn.execute(
        '''
        UPDATE players
        SET hp=?, location_id=?, in_battle=0, pvp_respawn_protection_until=?
        WHERE telegram_id=?
        ''',
        (max(1, int(max_hp * 0.30)), respawn_hub, int(_utc_now().timestamp()) + RESPAWN_PROTECTION_WINDOW_SECONDS, loser_id),
    )
    conn.commit()
    conn.close()


def _persist_winner_remaining_state(*, winner_id: int, payload: dict, engagement_row) -> None:
    battle = payload.get('battle') or {}
    attacker_id = int(engagement_row['attacker_id'])
    if winner_id == attacker_id:
        hp = int(battle.get('attacker_hp', 1))
        mana = int(battle.get('attacker_mana', 0))
    else:
        hp = int(battle.get('defender_hp', 1))
        mana = int(battle.get('defender_mana', 0))
    conn = get_connection()
    conn.execute(
        'UPDATE players SET hp=?, mana=?, in_battle=0 WHERE telegram_id=?',
        (max(1, hp), max(0, mana), winner_id),
    )
    conn.commit()
    conn.close()


def _finalize_pvp_battle(*, engagement_row, payload: dict, winner_id: int, loser_id: int) -> None:
    payload.setdefault('battle', {})['state'] = PVP_BATTLE_STATE_FINISHED
    repeat_kill_count, transfer_scale = _resolve_repeat_kill_dampening(winner_id=winner_id, loser_id=loser_id)
    conn = get_connection()
    winner_row = conn.execute('SELECT * FROM players WHERE telegram_id=?', (winner_id,)).fetchone()
    loser_row = conn.execute('SELECT * FROM players WHERE telegram_id=?', (loser_id,)).fetchone()
    initiator_row = conn.execute('SELECT * FROM players WHERE telegram_id=?', (int(engagement_row['attacker_id']),)).fetchone()
    initial_target_row = conn.execute('SELECT * FROM players WHERE telegram_id=?', (int(engagement_row['defender_id']),)).fetchone()
    winner = dict(winner_row) if winner_row else {'telegram_id': winner_id}
    loser = dict(loser_row) if loser_row else {'telegram_id': loser_id}
    initiator = dict(initiator_row) if initiator_row else {'telegram_id': int(engagement_row['attacker_id'])}
    initial_target = dict(initial_target_row) if initial_target_row else {'telegram_id': int(engagement_row['defender_id'])}
    infamy_delta = resolve_kill_infamy_delta(
        winner=winner,
        loser=loser,
        initiator=initiator,
        initial_target=initial_target,
        location_id=str(engagement_row['location_id']),
        repeat_kill_count=repeat_kill_count,
    )
    conn.execute(
        '''
        INSERT INTO pvp_log (attacker_id, defender_id, winner_id, exp_gained, gold_gained)
        VALUES (?, ?, ?, 0, 0)
        ''',
        (engagement_row['attacker_id'], engagement_row['defender_id'], winner_id),
    )
    conn.execute(
        'UPDATE players SET in_battle=0 WHERE telegram_id IN (?, ?)',
        (engagement_row['attacker_id'], engagement_row['defender_id']),
    )
    if infamy_delta > 0:
        conn.execute(
            'UPDATE players SET infamy=infamy+?, red_flag=1 WHERE telegram_id=?',
            (infamy_delta, winner_id),
        )
    conn.commit()
    conn.close()

    _transfer_vulnerable_inventory(
        winner_id=winner_id,
        loser_id=loser_id,
        location_id=str(engagement_row['location_id']),
        transfer_scale=transfer_scale,
    )
    _apply_pvp_defeat(
        loser_id=loser_id,
        location_id=str(engagement_row['location_id']),
    )
    _persist_winner_remaining_state(
        winner_id=winner_id,
        payload=payload,
        engagement_row=engagement_row,
    )
    _write_engagement_state(
        engagement_id=int(engagement_row['id']),
        state=ENGAGEMENT_STATE_CANCELLED,
        payload=payload,
    )


def apply_illegal_aggression_penalties(*, attacker_id: int) -> None:
    conn = get_connection()
    attacker = conn.execute('SELECT * FROM players WHERE telegram_id=?', (attacker_id,)).fetchone()
    defender_id = None
    current_row = conn.execute(
        '''
        SELECT defender_id, location_id
        FROM pvp_engagements
        WHERE attacker_id=?
          AND engagement_state IN (?, ?, ?)
        ORDER BY id DESC
        LIMIT 1
        ''',
        (attacker_id, ENGAGEMENT_STATE_PENDING, 'active', ENGAGEMENT_STATE_CONVERTED_TO_BATTLE),
    ).fetchone()
    location_id = None
    if current_row:
        defender_id = int(current_row['defender_id'])
        location_id = str(current_row['location_id'])
    defender = conn.execute('SELECT * FROM players WHERE telegram_id=?', (defender_id,)).fetchone() if defender_id else None
    infamy_delta = resolve_illegal_aggression_infamy(
        attacker=dict(attacker) if attacker else {'telegram_id': attacker_id},
        defender=dict(defender) if defender else {'telegram_id': defender_id or 0},
        location_id=location_id,
    )
    conn.execute(
        '''
        UPDATE players
        SET red_flag=1,
            infamy=infamy + ?
        WHERE telegram_id=?
        ''',
        (max(1, infamy_delta), attacker_id),
    )
    conn.commit()
    conn.close()


def process_live_pvp_due_events(*, now: datetime | None = None) -> list[dict]:
    events: list[dict] = []
    check_now = now or _utc_now()
    conn = get_connection()
    rows = conn.execute(
        '''
        SELECT * FROM pvp_engagements
        WHERE engagement_state IN (?, ?, ?)
        ORDER BY id ASC
        ''',
        (ENGAGEMENT_STATE_PENDING, 'active', ENGAGEMENT_STATE_CONVERTED_TO_BATTLE),
    ).fetchall()
    conn.close()

    for row in rows:
        if row['engagement_state'] in {ENGAGEMENT_STATE_PENDING, 'active'}:
            state, payload = advance_engagement_to_live_battle_if_ready(row, now=check_now)
            if state == ENGAGEMENT_STATE_CONVERTED_TO_BATTLE:
                events.append({'type': 'engagement_live', 'row': row, 'payload': payload})
            continue

        payload = _deserialize_reason_context(row['reason_context'])
        battle = payload.get('battle') or {}
        if battle.get('state') != PVP_BATTLE_STATE_LIVE:
            continue
        if _from_iso(battle['turn_started_at']) > check_now:
            continue
        if actor_id := int(battle.get('turn_owner', 0)):
            status, updated_payload = resolve_live_battle_turn(row, actor_id=actor_id, selected_action_id=None)
            if status in {'resolved', 'finished'}:
                events.append({'type': 'turn_auto_resolved', 'row': row, 'payload': updated_payload, 'status': status})
    return events


async def run_live_pvp_tick(bot) -> None:
    for event in process_live_pvp_due_events():
        row = event['row']
        if event['type'] == 'engagement_live':
            for player_id in (int(row['attacker_id']), int(row['defender_id'])):
                lang = get_player_lang(player_id)
                try:
                    await bot.send_message(player_id, t('location.pvp_turn_auto_notice', lang))
                except Exception:
                    pass
        if event['type'] == 'turn_auto_resolved' and event.get('status') == 'finished':
            winner_id = None
            battle = (event.get('payload') or {}).get('battle') or {}
            if battle.get('attacker_hp', 0) > 0:
                winner_id = int(row['attacker_id'])
            elif battle.get('defender_hp', 0) > 0:
                winner_id = int(row['defender_id'])
            for player_id in (int(row['attacker_id']), int(row['defender_id'])):
                lang = get_player_lang(player_id)
                msg_key = 'location.pvp_battle_finished'
                if winner_id == player_id:
                    msg_key = 'location.pvp_win_notice'
                try:
                    await bot.send_message(player_id, t(msg_key, lang))
                except Exception:
                    pass
