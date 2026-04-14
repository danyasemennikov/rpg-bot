from __future__ import annotations

import json
import uuid
import zlib
from datetime import datetime, timedelta, timezone

from database import get_connection
from game.balance import (
    normalize_armor_class,
    normalize_encumbrance,
    normalize_offhand_profile,
    normalize_weapon_profile,
)
from game.equipment_stats import get_equipped_item_ids, get_player_effective_stats
from game.itemization import get_item_archetype_metadata
from game.items_data import get_item, get_item_encumbrance
from game.locations import get_location
from game.live_combat_runtime import (
    DEFAULT_SIDE_TURN_TIMEOUT_SECONDS,
    EncounterRuntimeState,
    LiveCombatRuntime,
    LiveCombatRuntimeStore,
)

SIDE_PLAYER = 'side_a'
SIDE_ENEMY = 'side_b'
SPAWN_STATE_IDLE = 'idle'
SPAWN_STATE_FORMING = 'forming'
SPAWN_STATE_ACTIVE = 'active'
SPAWN_STATE_RESPAWNING = 'respawning'
DEFAULT_WORLD_SPAWN_RESPAWN_SECONDS = 30
FORMING_ENCOUNTER_TTL_SECONDS = 90

_SOLO_PVE_RUNTIME_STORE = LiveCombatRuntimeStore()
_SOLO_PVE_RUNTIME = LiveCombatRuntime(_SOLO_PVE_RUNTIME_STORE)


class OpenWorldRuntimeStartBlocked(RuntimeError):
    """First anchored open-world runtime start cannot proceed without atomic lock."""

PARTICIPANT_COMBAT_SNAPSHOT_FIELDS = (
    'player_hp',
    'player_mana',
    'player_dead',
    'player_max_hp',
    'player_max_mana',
    'weapon_id',
    'weapon_type',
    'weapon_profile',
    'weapon_damage',
    'armor_class',
    'offhand_profile',
    'encumbrance',
    'effective_strength',
    'effective_agility',
    'effective_intuition',
    'effective_vitality',
    'effective_wisdom',
    'effective_luck',
    'equipment_physical_defense_bonus',
    'equipment_magic_defense_bonus',
    'equipment_accuracy_bonus',
    'equipment_evasion_bonus',
    'equipment_block_chance_bonus',
    'equipment_magic_power_bonus',
    'equipment_healing_power_bonus',
    'defense_buff_turns',
    'defense_buff_value',
    'defense_buff_source',
    'berserk_turns',
    'berserk_damage',
    'berserk_defense_penalty_turns',
    'berserk_defense_penalty',
    'blessing_turns',
    'blessing_value',
    'regen_turns',
    'regen_amount',
    'resurrection_active',
    'resurrection_hp',
    'resurrection_turns',
    'parry_active',
    'parry_value',
    'invincible_turns',
    'dodge_buff_turns',
    'dodge_buff_value',
    'guaranteed_crit_turns',
    'steady_aim_turns',
    'steady_aim_value',
    'press_the_line_turns',
    'press_the_line_value',
    'feint_step_turns',
    'feint_step_value',
    'arcane_surge_turns',
    'arcane_surge_value',
    'executioner_focus_turns',
    'executioner_focus_value',
    'battle_stance_turns',
    'battle_stance_value',
    'spell_echo_turns',
    'spell_echo_value',
    'quick_channel_turns',
    'quick_channel_value',
    'hunters_mark_turns',
    'vulnerability_turns',
    'vulnerability_value',
    'vulnerability_source',
    'disarm_turns',
    'disarm_value',
    'weaken_turns',
    'weaken_value',
    'fire_shield_turns',
    'fire_shield_value',
)


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
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS pve_encounter_participants (
            encounter_id  TEXT NOT NULL,
            player_id     INTEGER NOT NULL,
            side_id       TEXT NOT NULL DEFAULT 'side_a',
            status        TEXT NOT NULL DEFAULT 'active',
            joined_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (encounter_id, player_id)
        )
        '''
    )
    conn.execute(
        '''
        CREATE INDEX IF NOT EXISTS idx_pve_encounter_participants_player_status
        ON pve_encounter_participants (player_id, status, encounter_id)
        '''
    )
    columns = {
        str(row['name'])
        for row in conn.execute("PRAGMA table_info('pve_encounters')").fetchall()
    }
    if 'location_id' not in columns:
        conn.execute("ALTER TABLE pve_encounters ADD COLUMN location_id TEXT")
    if 'anchor_spawn_instance_id' not in columns:
        conn.execute("ALTER TABLE pve_encounters ADD COLUMN anchor_spawn_instance_id TEXT")
    conn.commit()
    conn.close()


def _ensure_world_spawn_table() -> None:
    conn = get_connection()
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS pve_spawn_instances (
            spawn_instance_id     TEXT PRIMARY KEY,
            location_id           TEXT NOT NULL,
            mob_id                TEXT NOT NULL,
            state                 TEXT NOT NULL,
            linked_encounter_id   TEXT,
            respawn_available_at  TIMESTAMP,
            created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
    )
    conn.execute(
        '''
        CREATE INDEX IF NOT EXISTS idx_pve_spawn_instances_location_state
        ON pve_spawn_instances (location_id, state, mob_id)
        '''
    )
    conn.execute(
        '''
        CREATE INDEX IF NOT EXISTS idx_pve_spawn_instances_encounter
        ON pve_spawn_instances (linked_encounter_id)
        '''
    )
    conn.commit()
    conn.close()


def _spawn_instance_id(*, location_id: str, mob_id: str, instance_index: int = 1) -> str:
    # Keep index=1 backward-compatible with legacy spawn ids used by existing callbacks/tests.
    if int(instance_index) <= 1:
        return f'spawn-{location_id}-{mob_id}'
    return f'spawn-{location_id}-{mob_id}-{int(instance_index)}'


def _resolve_world_spawn_count(*, location: dict, mob_id: str) -> int:
    raw_map = location.get('world_spawn_counts')
    if not isinstance(raw_map, dict):
        return 1
    raw_value = raw_map.get(mob_id)
    try:
        count = int(raw_value)
    except (TypeError, ValueError):
        return 1
    return max(1, count)


def _refresh_respawning_spawns_for_location(*, location_id: str) -> None:
    if not location_id:
        return
    _ensure_world_spawn_table()
    conn = get_connection()
    conn.execute(
        '''
        UPDATE pve_spawn_instances
        SET state=?, linked_encounter_id=NULL, respawn_available_at=NULL, updated_at=CURRENT_TIMESTAMP
        WHERE location_id=?
          AND state=?
          AND respawn_available_at IS NOT NULL
          AND respawn_available_at <= CURRENT_TIMESTAMP
        ''',
        (SPAWN_STATE_IDLE, location_id, SPAWN_STATE_RESPAWNING),
    )
    conn.commit()
    conn.close()


def ensure_location_pve_spawn_instances(*, location_id: str) -> None:
    if not location_id:
        return
    _ensure_world_spawn_table()
    location = get_location(location_id) or {}
    mob_ids = [str(mob_id) for mob_id in location.get('mobs', []) if isinstance(mob_id, str) and mob_id]
    if not mob_ids:
        _refresh_respawning_spawns_for_location(location_id=location_id)
        return

    conn = get_connection()
    for mob_id in mob_ids:
        spawn_count = _resolve_world_spawn_count(location=location, mob_id=mob_id)
        for index in range(1, spawn_count + 1):
            conn.execute(
                '''
                INSERT OR IGNORE INTO pve_spawn_instances (
                    spawn_instance_id, location_id, mob_id, state, linked_encounter_id, respawn_available_at
                ) VALUES (?, ?, ?, ?, NULL, NULL)
                ''',
                (
                    _spawn_instance_id(location_id=location_id, mob_id=mob_id, instance_index=index),
                    location_id,
                    mob_id,
                    SPAWN_STATE_IDLE,
                ),
            )
    conn.commit()
    conn.close()
    _refresh_respawning_spawns_for_location(location_id=location_id)


def list_location_available_spawn_instances(*, location_id: str) -> list[dict]:
    ensure_location_pve_spawn_instances(location_id=location_id)
    conn = get_connection()
    rows = conn.execute(
        '''
        SELECT spawn_instance_id, location_id, mob_id, state
        FROM pve_spawn_instances
        WHERE location_id=? AND state=?
        ORDER BY mob_id ASC, spawn_instance_id ASC
        ''',
        (location_id, SPAWN_STATE_IDLE),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def _prune_expired_forming_encounters(
    conn,
    *,
    location_id: str | None = None,
    encounter_id: str | None = None,
) -> list[str]:
    if not _table_exists(conn, 'pve_encounters') or not _table_exists(conn, 'pve_spawn_instances'):
        return []

    filters = [
        "e.status='active'",
        "e.anchor_spawn_instance_id IS NOT NULL",
        "s.linked_encounter_id = e.encounter_id",
        "s.state=?",
        "e.created_at <= datetime('now', ?)",
    ]
    params: list[object] = [
        SPAWN_STATE_FORMING,
        f'-{FORMING_ENCOUNTER_TTL_SECONDS} seconds',
    ]
    if location_id:
        filters.append('e.location_id=?')
        params.append(str(location_id))
    if encounter_id:
        filters.append('e.encounter_id=?')
        params.append(str(encounter_id))

    rows = conn.execute(
        f'''
        SELECT e.encounter_id
        FROM pve_encounters e
        JOIN pve_spawn_instances s ON s.spawn_instance_id = e.anchor_spawn_instance_id
        WHERE {' AND '.join(filters)}
        ''',
        tuple(params),
    ).fetchall()
    expired_ids = [str(row['encounter_id']) for row in rows]
    if not expired_ids:
        return []

    placeholders = ','.join('?' for _ in expired_ids)
    conn.execute(
        f'''
        UPDATE pve_encounters
        SET status='expired', updated_at=CURRENT_TIMESTAMP, finished_at=CURRENT_TIMESTAMP
        WHERE encounter_id IN ({placeholders})
          AND status='active'
        ''',
        tuple(expired_ids),
    )
    if _table_exists(conn, 'pve_encounter_participants'):
        conn.execute(
            f'''
            UPDATE pve_encounter_participants
            SET status='expired', updated_at=CURRENT_TIMESTAMP
            WHERE encounter_id IN ({placeholders})
              AND status='active'
            ''',
            tuple(expired_ids),
        )
    conn.execute(
        f'''
        UPDATE pve_spawn_instances
        SET state=?, linked_encounter_id=NULL, respawn_available_at=NULL, updated_at=CURRENT_TIMESTAMP
        WHERE linked_encounter_id IN ({placeholders})
          AND state=?
        ''',
        (SPAWN_STATE_IDLE, *expired_ids, SPAWN_STATE_FORMING),
    )
    return expired_ids


def list_location_active_pve_encounters(*, location_id: str) -> list[dict]:
    _ensure_pve_encounter_table()
    ensure_location_pve_spawn_instances(location_id=location_id)
    conn = get_connection()
    expired_ids = _prune_expired_forming_encounters(conn, location_id=location_id)
    if expired_ids:
        conn.commit()
    rows = conn.execute(
        '''
        SELECT e.encounter_id, e.mob_id, e.location_id, e.anchor_spawn_instance_id, s.state AS spawn_state
        FROM pve_encounters e
        JOIN pve_spawn_instances s ON s.spawn_instance_id = e.anchor_spawn_instance_id
        WHERE e.status='active'
          AND e.location_id=?
          AND e.anchor_spawn_instance_id IS NOT NULL
          AND s.linked_encounter_id = e.encounter_id
          AND s.state IN (?, ?)
        ORDER BY e.created_at DESC
        ''',
        (location_id, SPAWN_STATE_FORMING, SPAWN_STATE_ACTIVE),
    ).fetchall()
    encounters: list[dict] = []
    for row in rows:
        encounter = dict(row)
        participant_count = conn.execute(
            '''
            SELECT COUNT(*) AS total
            FROM pve_encounter_participants
            WHERE encounter_id=? AND status='active' AND side_id=?
            ''',
            (encounter['encounter_id'], SIDE_PLAYER),
        ).fetchone()
        participant_rows = conn.execute(
            '''
            SELECT player_id
            FROM pve_encounter_participants
            WHERE encounter_id=? AND status='active' AND side_id=?
            ORDER BY joined_at ASC, player_id ASC
            ''',
            (encounter['encounter_id'], SIDE_PLAYER),
        ).fetchall()
        encounter['participant_count'] = int(participant_count['total']) if participant_count else 0
        encounter['participant_player_ids'] = [int(participant['player_id']) for participant in participant_rows]
        encounter['joinable'] = str(encounter.get('spawn_state') or '') == SPAWN_STATE_FORMING
        encounters.append(encounter)
    conn.close()
    return encounters


def get_open_world_pve_encounter_detail(*, encounter_id: str) -> dict | None:
    if not encounter_id:
        return None
    conn = get_connection()
    if not _table_exists(conn, 'pve_encounters') or not _table_exists(conn, 'pve_spawn_instances'):
        conn.close()
        return None
    if not _table_exists(conn, 'pve_encounter_participants'):
        conn.close()
        return None
    expired_ids = _prune_expired_forming_encounters(conn, encounter_id=encounter_id)
    if expired_ids:
        conn.commit()
    encounter_row = conn.execute(
        '''
        SELECT e.encounter_id, e.status, e.mob_id, e.location_id, e.anchor_spawn_instance_id, s.state AS spawn_state
        FROM pve_encounters e
        JOIN pve_spawn_instances s ON s.spawn_instance_id = e.anchor_spawn_instance_id
        WHERE e.encounter_id=?
          AND e.status='active'
          AND e.anchor_spawn_instance_id IS NOT NULL
          AND s.linked_encounter_id = e.encounter_id
          AND s.state IN (?, ?)
        LIMIT 1
        ''',
        (encounter_id, SPAWN_STATE_FORMING, SPAWN_STATE_ACTIVE),
    ).fetchone()
    if not encounter_row:
        conn.close()
        return None
    participant_count = conn.execute(
        '''
        SELECT COUNT(*) AS total
        FROM pve_encounter_participants
        WHERE encounter_id=? AND status='active' AND side_id=?
        ''',
        (encounter_id, SIDE_PLAYER),
    ).fetchone()
    participant_rows = conn.execute(
        '''
        SELECT player_id
        FROM pve_encounter_participants
        WHERE encounter_id=? AND status='active' AND side_id=?
        ORDER BY joined_at ASC, player_id ASC
        ''',
        (encounter_id, SIDE_PLAYER),
    ).fetchall()
    conn.close()
    detail = dict(encounter_row)
    detail['participant_count'] = int(participant_count['total']) if participant_count else 0
    detail['participant_player_ids'] = [int(row['player_id']) for row in participant_rows]
    detail['joinable'] = str(detail.get('spawn_state') or '') == SPAWN_STATE_FORMING
    return detail


def can_join_open_world_pve_encounter(*, encounter_id: str, player_id: int) -> tuple[bool, str]:
    if not encounter_id:
        return False, 'not_found'

    conn = get_connection()
    if not _table_exists(conn, 'players'):
        conn.close()
        return False, 'not_found'
    if not _table_exists(conn, 'pve_encounters') or not _table_exists(conn, 'pve_spawn_instances'):
        conn.close()
        return False, 'not_found'
    if not _table_exists(conn, 'pve_encounter_participants'):
        conn.close()
        return False, 'not_found'
    player_row = conn.execute(
        'SELECT telegram_id, location_id, in_battle FROM players WHERE telegram_id=? LIMIT 1',
        (int(player_id),),
    ).fetchone()
    if not player_row:
        conn.close()
        return False, 'not_found'
    expired_ids = _prune_expired_forming_encounters(
        conn,
        encounter_id=encounter_id,
    )
    if expired_ids:
        conn.commit()

    encounter_row = conn.execute(
        '''
        SELECT e.encounter_id, e.location_id, s.state AS spawn_state
        FROM pve_encounters e
        JOIN pve_spawn_instances s ON s.spawn_instance_id = e.anchor_spawn_instance_id
        WHERE e.encounter_id=?
          AND e.status='active'
          AND e.anchor_spawn_instance_id IS NOT NULL
          AND s.linked_encounter_id = e.encounter_id
          AND s.state IN (?, ?)
        LIMIT 1
        ''',
        (encounter_id, SPAWN_STATE_FORMING, SPAWN_STATE_ACTIVE),
    ).fetchone()
    if not encounter_row:
        conn.close()
        return False, 'not_found'

    if str(encounter_row['spawn_state']) != SPAWN_STATE_FORMING:
        conn.close()
        return False, 'locked'

    if str(player_row['location_id'] or '') != str(encounter_row['location_id'] or ''):
        conn.close()
        return False, 'wrong_location'

    already_joined = conn.execute(
        '''
        SELECT 1
        FROM pve_encounter_participants
        WHERE encounter_id=? AND player_id=? AND status='active'
        LIMIT 1
        ''',
        (encounter_id, int(player_id)),
    ).fetchone()
    if already_joined:
        conn.close()
        return False, 'already_joined'

    active_row = conn.execute(
        '''
        SELECT e.encounter_id
        FROM pve_encounters e
        JOIN pve_encounter_participants p ON p.encounter_id = e.encounter_id
        WHERE p.player_id=? AND p.status='active' AND e.status='active'
        ORDER BY e.created_at DESC
        LIMIT 1
        ''',
        (int(player_id),),
    ).fetchone()
    active_encounter = str(active_row['encounter_id']) if active_row else None
    if active_encounter and str(active_encounter) != str(encounter_id):
        conn.close()
        return False, 'busy'

    if int(player_row['in_battle'] or 0) == 1 and not active_encounter:
        conn.close()
        return False, 'busy'

    conn.close()
    return True, 'ok'


def join_open_world_pve_encounter(*, encounter_id: str, player_id: int) -> tuple[bool, str]:
    conn = get_connection()
    try:
        if not _table_exists(conn, 'players'):
            return False, 'not_found'
        if not _table_exists(conn, 'pve_encounters') or not _table_exists(conn, 'pve_spawn_instances'):
            return False, 'not_found'
        if not _table_exists(conn, 'pve_encounter_participants'):
            return False, 'not_found'
        conn.execute('BEGIN IMMEDIATE')
        player_row = conn.execute(
            'SELECT telegram_id, location_id, in_battle FROM players WHERE telegram_id=? LIMIT 1',
            (int(player_id),),
        ).fetchone()
        if not player_row:
            conn.rollback()
            return False, 'not_found'
        expired_ids = _prune_expired_forming_encounters(conn, encounter_id=encounter_id)
        if expired_ids:
            conn.commit()
            return False, 'not_found'

        encounter_row = conn.execute(
            '''
            SELECT e.encounter_id, e.location_id, s.state AS spawn_state
            FROM pve_encounters e
            JOIN pve_spawn_instances s ON s.spawn_instance_id = e.anchor_spawn_instance_id
            WHERE e.encounter_id=?
              AND e.status='active'
              AND e.anchor_spawn_instance_id IS NOT NULL
              AND s.linked_encounter_id = e.encounter_id
              AND s.state IN (?, ?)
            LIMIT 1
            ''',
            (encounter_id, SPAWN_STATE_FORMING, SPAWN_STATE_ACTIVE),
        ).fetchone()
        if not encounter_row:
            conn.rollback()
            return False, 'not_found'
        if str(encounter_row['spawn_state']) != SPAWN_STATE_FORMING:
            conn.rollback()
            return False, 'locked'
        if str(player_row['location_id'] or '') != str(encounter_row['location_id'] or ''):
            conn.rollback()
            return False, 'wrong_location'

        already_joined = conn.execute(
            '''
            SELECT 1
            FROM pve_encounter_participants
            WHERE encounter_id=? AND player_id=? AND status='active'
            LIMIT 1
            ''',
            (encounter_id, int(player_id)),
        ).fetchone()
        if already_joined:
            conn.rollback()
            return False, 'already_joined'

        active_row = conn.execute(
            '''
            SELECT e.encounter_id
            FROM pve_encounters e
            JOIN pve_encounter_participants p ON p.encounter_id = e.encounter_id
            WHERE p.player_id=? AND p.status='active' AND e.status='active'
            ORDER BY e.created_at DESC
            LIMIT 1
            ''',
            (int(player_id),),
        ).fetchone()
        active_encounter = str(active_row['encounter_id']) if active_row else None
        if active_encounter and str(active_encounter) != str(encounter_id):
            conn.rollback()
            return False, 'busy'

        if int(player_row['in_battle'] or 0) == 1 and not active_encounter:
            conn.rollback()
            return False, 'busy'

        conn.execute(
            '''
            INSERT INTO pve_encounter_participants (encounter_id, player_id, side_id, status)
            VALUES (?, ?, ?, 'active')
            ''',
            (encounter_id, int(player_id), SIDE_PLAYER),
        )
        conn.commit()
        return True, 'joined'
    finally:
        conn.close()


def leave_open_world_pve_encounter(*, encounter_id: str, player_id: int) -> tuple[bool, str]:
    if not encounter_id:
        return False, 'not_found'

    conn = get_connection()
    try:
        if not _table_exists(conn, 'pve_encounters') or not _table_exists(conn, 'pve_spawn_instances'):
            return False, 'not_found'
        if not _table_exists(conn, 'pve_encounter_participants'):
            return False, 'not_found'
        conn.execute('BEGIN IMMEDIATE')
        expired_ids = _prune_expired_forming_encounters(conn, encounter_id=encounter_id)
        if expired_ids:
            conn.commit()
            return False, 'not_found'
        encounter_row = conn.execute(
            '''
            SELECT e.encounter_id, s.state AS spawn_state
            FROM pve_encounters e
            JOIN pve_spawn_instances s ON s.spawn_instance_id = e.anchor_spawn_instance_id
            WHERE e.encounter_id=?
              AND e.status='active'
              AND e.anchor_spawn_instance_id IS NOT NULL
              AND s.linked_encounter_id = e.encounter_id
              AND s.state IN (?, ?)
            LIMIT 1
            ''',
            (encounter_id, SPAWN_STATE_FORMING, SPAWN_STATE_ACTIVE),
        ).fetchone()
        if not encounter_row:
            conn.rollback()
            return False, 'not_found'
        if str(encounter_row['spawn_state']) != SPAWN_STATE_FORMING:
            conn.rollback()
            return False, 'locked'

        active_participant = conn.execute(
            '''
            SELECT 1
            FROM pve_encounter_participants
            WHERE encounter_id=? AND player_id=? AND side_id=? AND status='active'
            LIMIT 1
            ''',
            (encounter_id, int(player_id), SIDE_PLAYER),
        ).fetchone()
        if not active_participant:
            conn.rollback()
            return False, 'not_joined'

        conn.execute(
            '''
            UPDATE pve_encounter_participants
            SET status='left', updated_at=CURRENT_TIMESTAMP
            WHERE encounter_id=? AND player_id=? AND side_id=? AND status='active'
            ''',
            (encounter_id, int(player_id), SIDE_PLAYER),
        )

        remaining_row = conn.execute(
            '''
            SELECT COUNT(*) AS total
            FROM pve_encounter_participants
            WHERE encounter_id=? AND side_id=? AND status='active'
            ''',
            (encounter_id, SIDE_PLAYER),
        ).fetchone()
        remaining_players = int(remaining_row['total']) if remaining_row else 0
        if remaining_players <= 0:
            conn.execute(
                '''
                UPDATE pve_encounters
                SET status='abandoned', updated_at=CURRENT_TIMESTAMP, finished_at=CURRENT_TIMESTAMP
                WHERE encounter_id=?
                ''',
                (encounter_id,),
            )
            conn.execute(
                '''
                UPDATE pve_spawn_instances
                SET state=?, linked_encounter_id=NULL, respawn_available_at=NULL, updated_at=CURRENT_TIMESTAMP
                WHERE linked_encounter_id=? AND state=?
                ''',
                (SPAWN_STATE_IDLE, encounter_id, SPAWN_STATE_FORMING),
            )
            conn.commit()
            return True, 'left_collapsed'

        conn.commit()
        return True, 'left'
    finally:
        conn.close()


def lock_open_world_pve_roster_for_runtime_start(*, encounter_id: str) -> list[int] | None:
    """
    Atomically finalize forming open-world encounter roster and lock spawn state.
    Returns locked final roster when FORMING->ACTIVE transition is performed.
    Returns None when encounter is not in joinable FORMING anchor-live state.
    """
    if not encounter_id:
        return None
    conn = get_connection()
    try:
        if not _table_exists(conn, 'pve_encounters') or not _table_exists(conn, 'pve_spawn_instances'):
            return None
        conn.execute('BEGIN IMMEDIATE')
        if not _table_exists(conn, 'pve_encounter_participants'):
            conn.rollback()
            return None
        expired_ids = _prune_expired_forming_encounters(conn, encounter_id=encounter_id)
        if expired_ids:
            conn.commit()
            return None
        anchor_row = conn.execute(
            '''
            SELECT s.spawn_instance_id
            FROM pve_encounters e
            JOIN pve_spawn_instances s ON s.spawn_instance_id = e.anchor_spawn_instance_id
            WHERE e.encounter_id=?
              AND e.status='active'
              AND e.anchor_spawn_instance_id IS NOT NULL
              AND s.linked_encounter_id = e.encounter_id
              AND s.state=?
            LIMIT 1
            ''',
            (encounter_id, SPAWN_STATE_FORMING),
        ).fetchone()
        if not anchor_row:
            conn.rollback()
            return None

        roster_rows = conn.execute(
            '''
            SELECT player_id
            FROM pve_encounter_participants
            WHERE encounter_id=? AND status='active' AND side_id=?
            ORDER BY joined_at ASC, player_id ASC
            ''',
            (encounter_id, SIDE_PLAYER),
        ).fetchall()
        final_roster = [int(row['player_id']) for row in roster_rows]

        updated = conn.execute(
            '''
            UPDATE pve_spawn_instances
            SET state=?, updated_at=CURRENT_TIMESTAMP
            WHERE spawn_instance_id=?
              AND linked_encounter_id=?
              AND state=?
            ''',
            (SPAWN_STATE_ACTIVE, str(anchor_row['spawn_instance_id']), encounter_id, SPAWN_STATE_FORMING),
        ).rowcount
        if updated <= 0:
            conn.rollback()
            return None

        conn.commit()
        return final_roster
    finally:
        conn.close()


def open_world_runtime_start_mode(*, encounter_id: str) -> str:
    if not encounter_id:
        return 'non_anchored'
    conn = get_connection()
    if not _table_exists(conn, 'pve_encounters'):
        conn.close()
        return 'non_anchored'
    expired_ids = _prune_expired_forming_encounters(conn, encounter_id=encounter_id)
    if expired_ids:
        conn.commit()
    encounter_row = conn.execute(
        '''
        SELECT anchor_spawn_instance_id
        FROM pve_encounters
        WHERE encounter_id=? AND status='active'
        LIMIT 1
        ''',
        (encounter_id,),
    ).fetchone()
    if not encounter_row:
        conn.close()
        # Legacy/non-anchored handler paths can carry synthetic encounter ids
        # that do not map to a real anchored world row. Treat these as normal
        # fallback runtime starts instead of blocking open-world contract.
        return 'non_anchored'
    anchor_spawn_instance_id = str(encounter_row['anchor_spawn_instance_id'] or '')
    if not anchor_spawn_instance_id:
        conn.close()
        return 'non_anchored'
    if not _table_exists(conn, 'pve_spawn_instances'):
        conn.close()
        return 'anchor_unavailable'

    anchor_row = conn.execute(
        '''
        SELECT state, linked_encounter_id
        FROM pve_spawn_instances
        WHERE spawn_instance_id=?
        LIMIT 1
        ''',
        (anchor_spawn_instance_id,),
    ).fetchone()
    conn.close()
    if not anchor_row:
        return 'anchor_unavailable'
    if str(anchor_row['linked_encounter_id'] or '') != str(encounter_id):
        return 'anchor_unavailable'

    spawn_state = str(anchor_row['state'] or '')
    if spawn_state == SPAWN_STATE_FORMING:
        return 'forming_lock_required'
    if spawn_state == SPAWN_STATE_ACTIVE:
        return 'active_resume'
    return 'anchor_unavailable'


def _claim_spawn_instance_for_encounter(
    *,
    encounter_id: str,
    location_id: str,
    mob_id: str,
    spawn_instance_id: str | None = None,
) -> str | None:
    _ensure_world_spawn_table()
    ensure_location_pve_spawn_instances(location_id=location_id)
    conn = get_connection()
    conn.execute('BEGIN IMMEDIATE')
    resolved_spawn_id = spawn_instance_id
    if resolved_spawn_id:
        updated = conn.execute(
            '''
            UPDATE pve_spawn_instances
            SET state=?, linked_encounter_id=?, updated_at=CURRENT_TIMESTAMP
            WHERE spawn_instance_id=?
              AND location_id=?
              AND mob_id=?
              AND state=?
              AND linked_encounter_id IS NULL
            ''',
            (SPAWN_STATE_FORMING, encounter_id, resolved_spawn_id, location_id, mob_id, SPAWN_STATE_IDLE),
        ).rowcount
    else:
        candidate = conn.execute(
            '''
            SELECT spawn_instance_id
            FROM pve_spawn_instances
            WHERE location_id=?
              AND mob_id=?
              AND state=?
              AND linked_encounter_id IS NULL
            ORDER BY spawn_instance_id ASC
            LIMIT 1
            ''',
            (location_id, mob_id, SPAWN_STATE_IDLE),
        ).fetchone()
        resolved_spawn_id = str(candidate['spawn_instance_id']) if candidate else ''
        updated = 0
        if resolved_spawn_id:
            updated = conn.execute(
                '''
                UPDATE pve_spawn_instances
                SET state=?, linked_encounter_id=?, updated_at=CURRENT_TIMESTAMP
                WHERE spawn_instance_id=?
                  AND location_id=?
                  AND mob_id=?
                  AND state=?
                  AND linked_encounter_id IS NULL
                ''',
                (SPAWN_STATE_FORMING, encounter_id, resolved_spawn_id, location_id, mob_id, SPAWN_STATE_IDLE),
            ).rowcount
    if updated <= 0:
        conn.rollback()
        conn.close()
        return None
    conn.commit()
    conn.close()
    return resolved_spawn_id


def _set_spawn_instance_state_for_encounter(
    *,
    encounter_id: str,
    state: str,
    clear_link: bool = False,
    respawn_seconds: int | None = None,
) -> None:
    _ensure_world_spawn_table()
    conn = get_connection()
    if clear_link:
        available_at = None
        if respawn_seconds and respawn_seconds > 0:
            available_at = (datetime.now(timezone.utc) + timedelta(seconds=respawn_seconds)).strftime('%Y-%m-%d %H:%M:%S')
        conn.execute(
            '''
            UPDATE pve_spawn_instances
            SET state=?, linked_encounter_id=NULL, respawn_available_at=?, updated_at=CURRENT_TIMESTAMP
            WHERE linked_encounter_id=?
            ''',
            (state, available_at, encounter_id),
        )
    else:
        conn.execute(
            '''
            UPDATE pve_spawn_instances
            SET state=?, updated_at=CURRENT_TIMESTAMP
            WHERE linked_encounter_id=?
            ''',
            (state, encounter_id),
        )
    conn.commit()
    conn.close()


def _transition_anchored_spawns_for_encounters(
    conn,
    *,
    encounter_ids: list[str],
    state: str,
    clear_link: bool,
    respawn_seconds: int | None = None,
) -> None:
    if not encounter_ids:
        return
    if not _table_exists(conn, 'pve_spawn_instances'):
        return
    placeholders = ','.join('?' for _ in encounter_ids)
    available_at = None
    if clear_link and respawn_seconds and respawn_seconds > 0:
        available_at = (datetime.now(timezone.utc) + timedelta(seconds=respawn_seconds)).strftime('%Y-%m-%d %H:%M:%S')

    if clear_link:
        conn.execute(
            f'''
            UPDATE pve_spawn_instances
            SET state=?, linked_encounter_id=NULL, respawn_available_at=?, updated_at=CURRENT_TIMESTAMP
            WHERE linked_encounter_id IN ({placeholders})
            ''',
            (state, available_at, *encounter_ids),
        )
        return

    conn.execute(
        f'''
        UPDATE pve_spawn_instances
        SET state=?, updated_at=CURRENT_TIMESTAMP
        WHERE linked_encounter_id IN ({placeholders})
        ''',
        (state, *encounter_ids),
    )


def _table_exists(conn, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table_name,),
    ).fetchone()
    return row is not None


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


def _deserialize_participant_state_map(raw_map: object) -> dict[str, dict]:
    if not isinstance(raw_map, dict):
        return {}
    normalized: dict[str, dict] = {}
    for raw_player_id, raw_state in raw_map.items():
        player_key = str(raw_player_id)
        if not isinstance(raw_state, dict):
            continue
        state = dict(raw_state)
        hp_value = int(state.get('player_hp', state.get('hp', 0)) or 0)
        mana_value = int(state.get('player_mana', state.get('mana', 0)) or 0)
        dead_value = bool(state.get('player_dead', state.get('defeated', False)) or hp_value <= 0)
        state['player_hp'] = hp_value
        state['player_mana'] = mana_value
        state['player_dead'] = dead_value
        state['hp'] = hp_value
        state['mana'] = mana_value
        state['defeated'] = dead_value
        normalized[player_key] = state
    return normalized


def _build_projection_snapshot_from_battle_state(*, battle_state: dict) -> dict:
    snapshot = {field: battle_state.get(field) for field in PARTICIPANT_COMBAT_SNAPSHOT_FIELDS}
    hp_value = int(snapshot.get('player_hp') or 0)
    mana_value = int(snapshot.get('player_mana') or 0)
    snapshot['player_hp'] = hp_value
    snapshot['player_mana'] = mana_value
    snapshot['player_dead'] = bool(snapshot.get('player_dead', hp_value <= 0))
    snapshot['player_max_hp'] = int(snapshot.get('player_max_hp') or hp_value)
    snapshot['player_max_mana'] = int(snapshot.get('player_max_mana') or mana_value)
    return snapshot


def _normalize_projection_snapshot(raw_state: dict, *, fallback_snapshot: dict) -> dict:
    normalized = dict(fallback_snapshot)
    for field in PARTICIPANT_COMBAT_SNAPSHOT_FIELDS:
        if field in raw_state:
            normalized[field] = raw_state.get(field)

    normalized['player_hp'] = max(0, int(normalized.get('player_hp') or 0))
    normalized['player_mana'] = max(0, int(normalized.get('player_mana') or 0))
    normalized['player_max_hp'] = max(int(normalized.get('player_max_hp') or normalized['player_hp']), normalized['player_hp'])
    normalized['player_max_mana'] = max(int(normalized.get('player_max_mana') or normalized['player_mana']), normalized['player_mana'])
    normalized['player_dead'] = bool(normalized.get('player_dead', False) or normalized['player_hp'] <= 0)
    return normalized


def _normalize_player_ids(player_ids: list[int]) -> list[int]:
    normalized = [int(pid) for pid in player_ids if int(pid) > 0]
    unique: list[int] = []
    seen: set[int] = set()
    for pid in normalized:
        if pid in seen:
            continue
        seen.add(pid)
        unique.append(pid)
    return unique


def _supersede_active_encounters_for_players(conn, player_ids: list[int]) -> None:
    if not player_ids:
        return

    placeholders = ','.join('?' for _ in player_ids)
    rows = conn.execute(
        f'''
        SELECT DISTINCT p.encounter_id
        FROM pve_encounter_participants p
        JOIN pve_encounters e ON e.encounter_id = p.encounter_id
        WHERE p.player_id IN ({placeholders})
          AND p.status='active'
          AND e.status='active'
        ''',
        tuple(player_ids),
    ).fetchall()
    encounter_ids = [str(row['encounter_id']) for row in rows]
    if not encounter_ids:
        return

    encounter_placeholders = ','.join('?' for _ in encounter_ids)
    conn.execute(
        f'''
        UPDATE pve_encounters
        SET status='superseded', updated_at=CURRENT_TIMESTAMP, finished_at=CURRENT_TIMESTAMP
        WHERE encounter_id IN ({encounter_placeholders})
        ''',
        tuple(encounter_ids),
    )
    conn.execute(
        f'''
        UPDATE pve_encounter_participants
        SET status='superseded', updated_at=CURRENT_TIMESTAMP
        WHERE encounter_id IN ({encounter_placeholders})
        ''',
        tuple(encounter_ids),
    )
    _transition_anchored_spawns_for_encounters(
        conn,
        encounter_ids=encounter_ids,
        state=SPAWN_STATE_RESPAWNING,
        clear_link=True,
        respawn_seconds=DEFAULT_WORLD_SPAWN_RESPAWN_SECONDS,
    )


def create_pve_encounter(
    *,
    owner_player_id: int,
    side_a_player_ids: list[int],
    battle_state: dict,
    mob: dict | None = None,
    encounter_id: str | None = None,
    location_id: str | None = None,
    anchor_spawn_instance_id: str | None = None,
) -> str:
    _ensure_pve_encounter_table()
    participant_ids = _normalize_player_ids(side_a_player_ids)
    if not participant_ids:
        raise ValueError('side_a_player_ids must include at least one player id.')

    owner_player_id = int(owner_player_id)
    if owner_player_id not in participant_ids:
        participant_ids.insert(0, owner_player_id)

    encounter_id = encounter_id or f'pve-enc-{uuid.uuid4().hex[:12]}'
    conn = get_connection()

    _supersede_active_encounters_for_players(conn, participant_ids)

    conn.execute(
        '''
        INSERT INTO pve_encounters (
            encounter_id, owner_player_id, status, mob_id, battle_state_json, mob_json, location_id, anchor_spawn_instance_id
        ) VALUES (?, ?, 'active', ?, ?, ?, ?, ?)
        ''',
        (
            encounter_id,
            owner_player_id,
            str(battle_state.get('mob_id') or (mob or {}).get('id') or ''),
            _serialize_payload(battle_state),
            _serialize_payload(mob or {}),
            str(location_id or battle_state.get('location_id') or ''),
            str(anchor_spawn_instance_id or battle_state.get('anchor_spawn_instance_id') or '') or None,
        ),
    )

    for player_id in participant_ids:
        conn.execute(
            '''
            INSERT INTO pve_encounter_participants (encounter_id, player_id, side_id, status)
            VALUES (?, ?, ?, 'active')
            ''',
            (encounter_id, int(player_id), SIDE_PLAYER),
        )

    conn.commit()
    conn.close()
    return encounter_id


def create_group_pve_encounter(*, player_ids: list[int], battle_state: dict, mob: dict | None = None) -> str:
    normalized_ids = _normalize_player_ids(player_ids)
    if not normalized_ids:
        raise ValueError('player_ids must include at least one player id.')
    return create_pve_encounter(
        owner_player_id=normalized_ids[0],
        side_a_player_ids=normalized_ids,
        battle_state=battle_state,
        mob=mob,
    )


def create_solo_pve_encounter(*, player_id: int, battle_state: dict, mob: dict | None = None) -> str:
    return create_pve_encounter(
        owner_player_id=int(player_id),
        side_a_player_ids=[int(player_id)],
        battle_state=battle_state,
        mob=mob,
    )


def create_or_load_open_world_pve_encounter(
    *,
    owner_player_id: int,
    location_id: str,
    mob_id: str,
    battle_state: dict,
    mob: dict | None = None,
    side_a_player_ids: list[int] | None = None,
    spawn_instance_id: str | None = None,
) -> tuple[str | None, str]:
    _ensure_pve_encounter_table()
    ensure_location_pve_spawn_instances(location_id=location_id)
    participant_ids = side_a_player_ids or [int(owner_player_id)]
    encounter_id = f'pve-enc-{uuid.uuid4().hex[:12]}'
    claimed_spawn_id = _claim_spawn_instance_for_encounter(
        encounter_id=encounter_id,
        location_id=location_id,
        mob_id=mob_id,
        spawn_instance_id=spawn_instance_id,
    )
    if not claimed_spawn_id:
        conn = get_connection()
        if spawn_instance_id:
            active_row = conn.execute(
                '''
                SELECT linked_encounter_id
                FROM pve_spawn_instances
                WHERE spawn_instance_id=?
                  AND location_id=?
                  AND mob_id=?
                  AND linked_encounter_id IS NOT NULL
                LIMIT 1
                ''',
                (
                    str(spawn_instance_id),
                    location_id,
                    mob_id,
                ),
            ).fetchone()
        else:
            active_row = conn.execute(
                '''
                SELECT linked_encounter_id
                FROM pve_spawn_instances
                WHERE location_id=?
                  AND mob_id=?
                  AND linked_encounter_id IS NOT NULL
                ORDER BY updated_at DESC
                LIMIT 1
                ''',
                (
                    location_id,
                    mob_id,
                ),
            ).fetchone()
        conn.close()
        if active_row and active_row['linked_encounter_id']:
            return str(active_row['linked_encounter_id']), 'spawn_busy'
        return None, 'spawn_unavailable'

    battle_state['location_id'] = location_id
    battle_state['anchor_spawn_instance_id'] = claimed_spawn_id
    battle_state['encounter_kind'] = 'pve'
    try:
        create_pve_encounter(
            owner_player_id=int(owner_player_id),
            side_a_player_ids=participant_ids,
            battle_state=battle_state,
            mob=mob,
            encounter_id=encounter_id,
            location_id=location_id,
            anchor_spawn_instance_id=claimed_spawn_id,
        )
    except Exception:
        _set_spawn_instance_state_for_encounter(
            encounter_id=encounter_id,
            state=SPAWN_STATE_IDLE,
            clear_link=True,
            respawn_seconds=None,
        )
        raise

    return encounter_id, 'created'


def get_active_pve_encounter_id_for_player(*, player_id: int, ensure_schema: bool = True) -> str | None:
    if ensure_schema:
        _ensure_pve_encounter_table()
    conn = get_connection()
    has_encounters = True
    has_participants = True
    if not ensure_schema:
        has_encounters = _table_exists(conn, 'pve_encounters')
        has_participants = _table_exists(conn, 'pve_encounter_participants')
        if not has_encounters:
            conn.close()
            return None

    if has_participants:
        row = conn.execute(
            '''
            SELECT e.encounter_id
            FROM pve_encounters e
            JOIN pve_encounter_participants p ON p.encounter_id = e.encounter_id
            WHERE p.player_id=? AND p.status='active' AND e.status='active'
            ORDER BY e.created_at DESC
            LIMIT 1
            ''',
            (player_id,),
        ).fetchone()
        if row:
            conn.close()
            return str(row['encounter_id'])

        legacy_row = conn.execute(
            '''
            SELECT encounter_id
            FROM pve_encounters
            WHERE owner_player_id=? AND status='active'
              AND NOT EXISTS (
                  SELECT 1
                  FROM pve_encounter_participants p
                  WHERE p.encounter_id = pve_encounters.encounter_id
              )
            ORDER BY created_at DESC
            LIMIT 1
            ''',
            (player_id,),
        ).fetchone()
    else:
        legacy_row = conn.execute(
            '''
            SELECT encounter_id
            FROM pve_encounters
            WHERE owner_player_id=? AND status='active'
            ORDER BY created_at DESC
            LIMIT 1
            ''',
            (player_id,),
        ).fetchone()

    if not legacy_row:
        conn.close()
        return None

    encounter_id = str(legacy_row['encounter_id'])
    if has_participants:
        participant_row = conn.execute(
            '''
            SELECT 1
            FROM pve_encounter_participants
            WHERE encounter_id=? AND player_id=?
            LIMIT 1
            ''',
            (encounter_id, int(player_id)),
        ).fetchone()
        if not participant_row:
            conn.execute(
                '''
                INSERT OR IGNORE INTO pve_encounter_participants (encounter_id, player_id, side_id, status)
                VALUES (?, ?, ?, 'active')
                ''',
                (encounter_id, int(player_id), SIDE_PLAYER),
            )
            conn.commit()
    conn.close()
    return encounter_id


def get_active_solo_pve_encounter_id(*, player_id: int) -> str | None:
    return get_active_pve_encounter_id_for_player(player_id=player_id)


def get_pve_encounter_player_ids(*, encounter_id: str, side_id: str = SIDE_PLAYER) -> list[int]:
    if not encounter_id:
        return []
    _ensure_pve_encounter_table()
    conn = get_connection()
    rows = conn.execute(
        '''
        SELECT player_id
        FROM pve_encounter_participants
        WHERE encounter_id=? AND status='active' AND side_id=?
        ORDER BY joined_at ASC, player_id ASC
        ''',
        (encounter_id, side_id),
    ).fetchall()
    conn.close()
    return [int(row['player_id']) for row in rows]


def load_active_pve_encounter(*, player_id: int | None = None, encounter_id: str | None = None) -> tuple[dict, dict] | None:
    _ensure_pve_encounter_table()
    resolved_encounter_id = encounter_id
    if not resolved_encounter_id and player_id is not None:
        resolved_encounter_id = get_active_pve_encounter_id_for_player(player_id=player_id)
    if not resolved_encounter_id:
        return None

    conn = get_connection()
    row = conn.execute(
        '''
        SELECT battle_state_json, mob_json
        FROM pve_encounters
        WHERE encounter_id=? AND status='active'
        ''',
        (resolved_encounter_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None

    battle_state = _deserialize_payload(row['battle_state_json'])
    battle_state.setdefault('pve_encounter_id', str(resolved_encounter_id))
    return battle_state, _deserialize_payload(row['mob_json'])


def load_active_solo_pve_encounter(*, player_id: int) -> tuple[dict, dict] | None:
    return load_active_pve_encounter(player_id=player_id)


def persist_solo_pve_encounter_state(*, encounter_id: str, battle_state: dict, mob: dict | None = None) -> None:
    if not encounter_id:
        return
    conn = get_connection()
    try:
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
    finally:
        conn.close()


def finish_solo_pve_encounter(*, player_id: int, encounter_id: str | None = None, status: str = 'finished') -> None:
    resolved_encounter_id = encounter_id or get_active_pve_encounter_id_for_player(player_id=player_id, ensure_schema=False)
    if resolved_encounter_id:
        conn = get_connection()
        try:
            conn.execute(
                '''
                UPDATE pve_encounters
                SET status=?, updated_at=CURRENT_TIMESTAMP, finished_at=CURRENT_TIMESTAMP
                WHERE encounter_id=?
                ''',
                (status, resolved_encounter_id),
            )
            if _table_exists(conn, 'pve_encounter_participants'):
                conn.execute(
                    '''
                    UPDATE pve_encounter_participants
                    SET status=?, updated_at=CURRENT_TIMESTAMP
                    WHERE encounter_id=? AND status='active'
                    ''',
                    (status, resolved_encounter_id),
                )
            _transition_anchored_spawns_for_encounters(
                conn,
                encounter_ids=[resolved_encounter_id],
                state=SPAWN_STATE_RESPAWNING,
                clear_link=True,
                respawn_seconds=DEFAULT_WORLD_SPAWN_RESPAWN_SECONDS,
            )
            conn.commit()
        finally:
            conn.close()
    clear_solo_pve_runtime(player_id=player_id, encounter_id=resolved_encounter_id)


def runtime_encounter_id(player_id: int, battle_state: dict | None = None) -> str | None:
    encounter_id = (battle_state or {}).get('pve_encounter_id')
    if encounter_id:
        return str(encounter_id)
    return get_active_pve_encounter_id_for_player(player_id=player_id)


def enemy_participant_id(encounter_id: str) -> int:
    return -(zlib.crc32(encounter_id.encode('utf-8')) or 1)


def reset_solo_pve_runtime_store() -> None:
    _SOLO_PVE_RUNTIME_STORE.reset()


def clear_solo_pve_runtime(player_id: int, encounter_id: str | None = None) -> None:
    resolved_encounter_id = encounter_id or runtime_encounter_id(player_id)
    if not resolved_encounter_id:
        return
    _SOLO_PVE_RUNTIME_STORE.remove(resolved_encounter_id)


def mark_group_participant_defeated(
    *,
    encounter_id: str,
    participant_id: int,
    status: str = 'defeated',
) -> None:
    if not encounter_id:
        return
    conn = get_connection()
    conn.execute(
        '''
        UPDATE pve_encounter_participants
        SET status=?, updated_at=CURRENT_TIMESTAMP
        WHERE encounter_id=? AND player_id=? AND status='active'
        ''',
        (status, encounter_id, int(participant_id)),
    )
    conn.commit()
    conn.close()

    runtime_state = _SOLO_PVE_RUNTIME_STORE.get(encounter_id)
    if runtime_state is None:
        return

    participant = runtime_state.participants.get(int(participant_id))
    if participant is not None:
        participant.phase_state = 'defeated'

    for side in runtime_state.sides.values():
        if int(participant_id) in side.participant_order:
            side.participant_order = [pid for pid in side.participant_order if pid != int(participant_id)]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _remaining_seconds(deadline: datetime | None, now: datetime | None = None) -> int | None:
    if not deadline:
        return None
    check_now = now or _utc_now()
    return max(0, int((deadline - check_now).total_seconds()))


def ensure_participant_combat_state(
    *,
    battle_state: dict,
    participant_ids: list[int],
    preferred_player_id: int | None = None,
) -> dict[str, dict]:
    participant_states = _deserialize_participant_state_map(battle_state.get('participant_states'))
    battle_state['participant_states'] = participant_states

    for participant_id in participant_ids:
        key = str(int(participant_id))
        current_raw = participant_states.get(key, {})
        participant_snapshot = _build_participant_bootstrap_snapshot_for_player(
            battle_state=battle_state,
            participant_id=int(participant_id),
        )
        current = _normalize_projection_snapshot(current_raw, fallback_snapshot=participant_snapshot)
        current['hp'] = current['player_hp']
        current['mana'] = current['player_mana']
        current['defeated'] = current['player_dead']
        participant_states[key] = current

    if preferred_player_id is not None:
        sync_projection_for_participant(battle_state=battle_state, player_id=preferred_player_id)
    return participant_states


def _build_participant_bootstrap_snapshot_for_player(*, battle_state: dict, participant_id: int) -> dict:
    fallback = _build_projection_snapshot_from_battle_state(battle_state=battle_state)
    conn = get_connection()
    row = conn.execute('SELECT * FROM players WHERE telegram_id=?', (int(participant_id),)).fetchone()
    conn.close()
    if not row:
        return fallback

    player = dict(row)
    effective = get_player_effective_stats(int(participant_id), player)
    equipped_ids = get_equipped_item_ids(int(participant_id))
    weapon_item = get_item(equipped_ids.get('weapon') or 'unarmed') if equipped_ids.get('weapon') else None
    offhand_item = get_item(equipped_ids.get('offhand')) if equipped_ids.get('offhand') else None
    chest_item = get_item(equipped_ids.get('chest')) if equipped_ids.get('chest') else None

    weapon_type = (weapon_item or {}).get('weapon_type', 'melee')
    weapon_profile = normalize_weapon_profile((weapon_item or {}).get('weapon_profile'), weapon_type)
    weapon_damage = int((weapon_item or {}).get('damage_min', (weapon_item or {}).get('damage', 10)) or 10)

    chest_meta = get_item_archetype_metadata(chest_item)
    offhand_meta = get_item_archetype_metadata(offhand_item)

    snapshot = dict(fallback)
    snapshot.update({
        'player_hp': int(player.get('hp', fallback.get('player_hp', 0)) or 0),
        'player_mana': int(player.get('mana', fallback.get('player_mana', 0)) or 0),
        'player_max_hp': int(effective.get('max_hp', fallback.get('player_max_hp', 1)) or 1),
        'player_max_mana': int(effective.get('max_mana', fallback.get('player_max_mana', 0)) or 0),
        'weapon_id': equipped_ids.get('weapon', 'unarmed') or 'unarmed',
        'weapon_type': weapon_type,
        'weapon_profile': weapon_profile,
        'weapon_damage': weapon_damage,
        'armor_class': normalize_armor_class(chest_meta.get('armor_class')),
        'offhand_profile': normalize_offhand_profile(offhand_meta.get('offhand_profile')),
        'encumbrance': normalize_encumbrance(get_item_encumbrance(chest_item) or get_item_encumbrance(offhand_item)),
        'effective_strength': int(effective.get('strength', player.get('strength', 1)) or 1),
        'effective_agility': int(effective.get('agility', player.get('agility', 1)) or 1),
        'effective_intuition': int(effective.get('intuition', player.get('intuition', 1)) or 1),
        'effective_vitality': int(effective.get('vitality', player.get('vitality', 1)) or 1),
        'effective_wisdom': int(effective.get('wisdom', player.get('wisdom', 1)) or 1),
        'effective_luck': int(effective.get('luck', player.get('luck', 1)) or 1),
        'equipment_physical_defense_bonus': int(effective.get('physical_defense_bonus', 0) or 0),
        'equipment_magic_defense_bonus': int(effective.get('magic_defense_bonus', 0) or 0),
        'equipment_accuracy_bonus': int(effective.get('accuracy_bonus', 0) or 0),
        'equipment_evasion_bonus': int(effective.get('evasion_bonus', 0) or 0),
        'equipment_block_chance_bonus': int(effective.get('block_chance_bonus', 0) or 0),
        'equipment_magic_power_bonus': int(effective.get('magic_power_bonus', 0) or 0),
        'equipment_healing_power_bonus': int(effective.get('healing_power_bonus', 0) or 0),
    })
    snapshot['player_dead'] = bool(snapshot.get('player_hp', 0) <= 0)
    return snapshot


def sync_projection_for_participant(*, battle_state: dict, player_id: int) -> None:
    participant_states = _deserialize_participant_state_map(battle_state.get('participant_states'))
    if not participant_states:
        return
    participant_key = str(int(player_id))
    participant_state = participant_states.get(participant_key)
    if not participant_state:
        return
    normalized = _normalize_projection_snapshot(participant_state, fallback_snapshot=_build_projection_snapshot_from_battle_state(battle_state=battle_state))
    for field in PARTICIPANT_COMBAT_SNAPSHOT_FIELDS:
        battle_state[field] = normalized.get(field)
    battle_state['player_hp'] = int(normalized.get('player_hp', battle_state.get('player_hp', 0)))
    battle_state['player_mana'] = int(normalized.get('player_mana', battle_state.get('player_mana', 0)))
    battle_state['player_dead'] = bool(normalized.get('player_dead', battle_state.get('player_hp', 0) <= 0))


def update_participant_combat_state_from_projection(*, battle_state: dict, player_id: int) -> None:
    participant_states = ensure_participant_combat_state(
        battle_state=battle_state,
        participant_ids=[player_id],
        preferred_player_id=None,
    )
    participant_key = str(int(player_id))
    participant_state = participant_states.setdefault(participant_key, {})
    snapshot = _build_projection_snapshot_from_battle_state(battle_state=battle_state)
    for field in PARTICIPANT_COMBAT_SNAPSHOT_FIELDS:
        participant_state[field] = snapshot.get(field)
    participant_state['hp'] = participant_state['player_hp']
    participant_state['mana'] = participant_state['player_mana']
    participant_state['defeated'] = participant_state['player_dead']


def run_with_participant_projection(
    *,
    battle_state: dict,
    participant_id: int,
    resolver,
):
    sync_projection_for_participant(battle_state=battle_state, player_id=participant_id)
    result = resolver()
    update_participant_combat_state_from_projection(battle_state=battle_state, player_id=participant_id)
    return result


def choose_enemy_target_participant_id(*, battle_state: dict) -> int | None:
    participant_states = _deserialize_participant_state_map(battle_state.get('participant_states'))
    roster: list[int] = []
    for raw_pid in battle_state.get('side_a_player_ids', []):
        try:
            roster.append(int(raw_pid))
        except (TypeError, ValueError):
            continue

    for participant_id in roster:
        state = participant_states.get(str(participant_id))
        if not state:
            return participant_id
        if int(state.get('hp', 0)) > 0 and not bool(state.get('defeated', False)):
            return participant_id
    return roster[0] if roster else None


def sync_battle_projection_from_runtime(
    *,
    battle_state: dict,
    runtime_state: EncounterRuntimeState,
    now: datetime | None = None,
) -> None:
    battle_state['runtime_encounter_id'] = runtime_state.encounter_id
    battle_state['active_side'] = runtime_state.active_side_id
    battle_state['turn_revision'] = int(runtime_state.turn_revision)
    battle_state['side_turn_state'] = runtime_state.side_turn_state
    battle_state['side_deadline_at'] = _to_iso(runtime_state.side_deadline_at)
    battle_state['side_remaining_seconds'] = _remaining_seconds(runtime_state.side_deadline_at, now=now)
    battle_state['round_index'] = int(runtime_state.round_index)

    side_a = runtime_state.sides.get(SIDE_PLAYER)
    side_a_order = list(side_a.participant_order if side_a else [])
    battle_state['side_a_player_ids'] = side_a_order
    battle_state['ally_commit_status'] = {
        str(pid): runtime_state.participants[pid].phase_state
        for pid in side_a_order
        if pid in runtime_state.participants
    }


def _sync_projection_targets(
    *,
    encounter_id: str,
    battle_state: dict | None = None,
    projection_states: list[dict] | None = None,
) -> None:
    runtime_state = _SOLO_PVE_RUNTIME_STORE.get(encounter_id)
    if runtime_state is None:
        return

    if battle_state is not None:
        sync_battle_projection_from_runtime(battle_state=battle_state, runtime_state=runtime_state)

    for target_state in projection_states or []:
        sync_battle_projection_from_runtime(battle_state=target_state, runtime_state=runtime_state)


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
        # Group PvE projection path: a second participant can open the same
        # encounter with an unsynced local cache. This must not reset runtime.
        pass

    side_a_players = get_pve_encounter_player_ids(encounter_id=encounter_id, side_id=SIDE_PLAYER)
    if not side_a_players:
        side_a_players = [int(player_id)]

    reset_runtime = False
    if runtime_state is not None:
        runtime_side = runtime_state.sides.get(SIDE_PLAYER)
        runtime_roster = list(runtime_side.participant_order if runtime_side else [])
        if runtime_roster != side_a_players:
            reset_runtime = True
        elif enemy_participant_id(encounter_id) not in runtime_state.participants:
            reset_runtime = True
    if reset_runtime:
        _SOLO_PVE_RUNTIME_STORE.remove(encounter_id)
        runtime_state = None

    if runtime_state is None:
        start_mode = open_world_runtime_start_mode(encounter_id=encounter_id)
        if start_mode == 'forming_lock_required':
            locked_roster = lock_open_world_pve_roster_for_runtime_start(encounter_id=encounter_id)
            if locked_roster is None:
                raise OpenWorldRuntimeStartBlocked('open_world_anchor_lock_failed')
            side_a_players = locked_roster
        elif start_mode == 'anchor_unavailable':
            raise OpenWorldRuntimeStartBlocked('open_world_anchor_unavailable')
        # start_mode == active_resume | non_anchored: no extra lock step required.

        runtime_state = _SOLO_PVE_RUNTIME.create_encounter(
            encounter_id=encounter_id,
            side_a_participants=side_a_players,
            side_b_participants=[enemy_participant_id(encounter_id)],
            active_side_id=SIDE_PLAYER,
        )
        runtime_state = _SOLO_PVE_RUNTIME.open_side_turn(encounter_id=encounter_id, now=check_now)
    elif runtime_state.side_turn_state == 'completed':
        runtime_state = _SOLO_PVE_RUNTIME.open_side_turn(encounter_id=encounter_id, now=check_now)

    ensure_participant_combat_state(
        battle_state=battle_state,
        participant_ids=side_a_players,
        preferred_player_id=player_id,
    )
    sync_battle_projection_from_runtime(battle_state=battle_state, runtime_state=runtime_state, now=check_now)
    return runtime_state


def _resolve_encounter_id(
    *,
    player_id: int | None = None,
    battle_state: dict | None = None,
    encounter_id: str | None = None,
) -> str | None:
    if encounter_id:
        return encounter_id
    if battle_state and battle_state.get('pve_encounter_id'):
        return str(battle_state['pve_encounter_id'])
    if player_id is None:
        return None
    return runtime_encounter_id(player_id, battle_state)


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
    _sync_projection_targets(encounter_id=encounter_id, battle_state=battle_state)
    return commit_result.accepted, commit_result.reason


def _resolve_batch_by_action(*, batch, on_player_action, on_enemy_action) -> None:
    for action in batch:
        if action.participant_id > 0:
            on_player_action(action)
        else:
            on_enemy_action(action)


def resolve_current_side_if_ready(
    *,
    player_id: int | None = None,
    encounter_id: str | None = None,
    battle_state: dict | None = None,
    projection_states: list[dict] | None = None,
    on_player_action,
    on_enemy_action,
) -> bool:
    encounter_id = _resolve_encounter_id(
        player_id=player_id,
        battle_state=battle_state,
        encounter_id=encounter_id,
    )
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
    _sync_projection_targets(encounter_id=encounter_id, battle_state=battle_state, projection_states=projection_states)
    return True


def resolve_due_player_timeout_if_any(
    *,
    player_id: int | None = None,
    encounter_id: str | None = None,
    battle_state: dict | None = None,
    projection_states: list[dict] | None = None,
    now: datetime | None = None,
    on_player_action=None,
) -> bool:
    encounter_id = _resolve_encounter_id(
        player_id=player_id,
        battle_state=battle_state,
        encounter_id=encounter_id,
    )
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
        encounter_id=encounter_id,
        battle_state=battle_state,
        projection_states=projection_states,
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
        battle_state=battle_state,
        now=now,
        on_player_action=on_player_timeout_action or (lambda _action: None),
    )
    if not timed_out:
        return False
    if not _encounter_continues_after_timeout_resolution(battle_state):
        return True

    run_enemy_instant_side(
        player_id=player_id,
        battle_state=battle_state,
        on_enemy_action=on_enemy_action or (lambda _action: None),
    )
    return True


def _encounter_continues_after_timeout_resolution(battle_state: dict) -> bool:
    if battle_state.get('mob_dead'):
        return False
    if bool(battle_state.get('resurrection_active')):
        return True

    side_player_ids = list(battle_state.get('side_a_player_ids') or [])
    participant_states = battle_state.get('participant_states') or {}
    if side_player_ids:
        for participant_id in side_player_ids:
            snapshot = participant_states.get(str(participant_id)) or {}
            if bool(snapshot.get('resurrection_active', False)):
                return True
            if bool(snapshot.get('defeated', False)):
                continue
            if bool(snapshot.get('player_dead', False)):
                continue
            hp_value = snapshot.get('player_hp', snapshot.get('hp', 1))
            if int(hp_value or 0) <= 0:
                continue
            return True
        return False

    return not bool(battle_state.get('player_dead'))


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
        battle_state=battle_state,
        on_player_action=lambda _action: None,
        on_enemy_action=on_enemy_action,
    )
    if not resolved:
        sync_battle_projection_from_runtime(battle_state=battle_state, runtime_state=runtime_state)
        return

    runtime_state = open_next_player_side_turn(player_id=player_id, battle_state=battle_state)
    sync_battle_projection_from_runtime(battle_state=battle_state, runtime_state=runtime_state)
