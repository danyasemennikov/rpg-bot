"""Durable two-transaction PvE victory reward settlement.

T1 freezes a complete deterministic plan with the terminal combat snapshot.
T2 applies that plan atomically.  Telegram I/O never occurs in either phase.
"""

from __future__ import annotations

import json
import logging
import random
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Callable

from database import get_connection
from game.balance import exp_to_next_level
from game.field_catalog import (
    DRY_STREAK_INCREMENT_BY_SPAWN_PROFILE,
    FIELD_DRY_STREAK_THRESHOLD,
    FIELD_MAX_TIER,
    FIELD_REWARD_POLICY_VERSION,
    GEAR_CHANCE_BY_SPAWN_PROFILE,
    LEGACY_REWARD_POLICY_VERSION,
    choose_field_item,
    choose_weighted_rarity,
    is_field_item,
    resolve_progress_route_id,
)
from game.gear_instances import (
    determine_mob_drop_item_tier,
    generate_secondary_rolls_for_item,
    grant_item_to_player,
)
from game.gear_progression import ensure_gear_progression_schema
from game.items_data import get_item
from game.mobs import MOBS
from game.open_world_reward_pools import clamp_rarity_to_quality_floor
from game.reward_source_metadata import (
    RewardSourceMetadata,
    build_open_world_combat_source_metadata,
    classify_item_reward_family,
    is_reward_family_allowed_for_source,
)
from game.enhancement_material_routing import resolve_enhancement_material_routing

SETTLEMENT_SCHEMA_VERSION = 1
SUPPORTED_POLICY_VERSIONS = {FIELD_REWARD_POLICY_VERSION, LEGACY_REWARD_POLICY_VERSION}
FailureHook = Callable[[str], None]
logger = logging.getLogger(__name__)


def _canonical_json(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _load_json(raw: str | None) -> dict:
    try:
        parsed = json.loads(raw or '{}')
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _participant_snapshot(battle_state: dict, player_id: int) -> dict:
    snapshots = battle_state.get('participant_states') or {}
    raw = snapshots.get(str(player_id), snapshots.get(player_id, {}))
    return dict(raw) if isinstance(raw, dict) else {}


def _locked_roster(conn, encounter: dict) -> tuple[list[int], dict[int, str]]:
    encounter_id = str(encounter['encounter_id'])
    participant_rows = conn.execute('''SELECT player_id, status FROM pve_encounter_participants
        WHERE encounter_id=? AND side_id='side_a' ORDER BY joined_at, player_id''', (encounter_id,)).fetchall()
    status_by_player = {int(row['player_id']): str(row['status']) for row in participant_rows}
    persisted = _load_json(encounter.get('locked_roster_json'))
    raw_locked = persisted.get('player_ids') if persisted else None
    if isinstance(raw_locked, list):
        locked = [int(player_id) for player_id in raw_locked]
    else:
        # Reviewed-head encounters predate locked_roster_json.  Leaving is only
        # legal while forming, so active/defeated rows are the recoverable lock.
        locked = [
            int(row['player_id']) for row in participant_rows
            if str(row['status']) in {'active', 'defeated'}
        ]
    if not locked or len(locked) != len(set(locked)):
        raise ValueError('invalid_locked_roster')
    if int(encounter['owner_player_id']) not in locked:
        raise ValueError('owner_not_in_locked_roster')
    if set(locked) != {
        player_id for player_id, status in status_by_player.items()
        if status in {'active', 'defeated'}
    }:
        raise ValueError('locked_roster_status_mismatch')
    return locked, status_by_player


def _validate_terminal_snapshot(*, conn, encounter: dict, supplied_state: dict, supplied_mob: dict) -> tuple[dict, dict]:
    """Return the authoritative persisted terminal state or reject T1."""
    encounter_id = str(encounter['encounter_id'])
    persisted_state = _load_json(encounter.get('battle_state_json'))
    persisted_mob = _load_json(encounter.get('mob_json'))
    if not persisted_state or _canonical_json(persisted_state) != _canonical_json(supplied_state):
        raise ValueError('terminal_snapshot_not_persisted')
    if str(persisted_state.get('pve_encounter_id') or '') != encounter_id:
        raise ValueError('terminal_encounter_identity_mismatch')
    encounter_mob_id = str(encounter.get('mob_id') or '')
    if not encounter_mob_id or str(persisted_mob.get('id') or supplied_mob.get('id') or '') != encounter_mob_id:
        raise ValueError('terminal_mob_identity_mismatch')
    if str(supplied_mob.get('id') or '') != encounter_mob_id:
        raise ValueError('terminal_supplied_mob_mismatch')

    locked_roster, status_by_player = _locked_roster(conn, encounter)
    participant_states = persisted_state.get('participant_states')
    if not isinstance(participant_states, dict):
        raise ValueError('terminal_participant_states_missing')
    snapshot_ids = {int(player_id) for player_id in participant_states if str(player_id).isdigit()}
    if snapshot_ids != set(locked_roster):
        raise ValueError('terminal_participant_roster_mismatch')
    active_projection = {int(player_id) for player_id in persisted_state.get('side_a_player_ids', [])}
    expected_active = {
        player_id for player_id in locked_roster if status_by_player.get(player_id) == 'active'
    }
    if active_projection != expected_active:
        raise ValueError('terminal_active_roster_mismatch')

    raw_units = list(persisted_state.get('enemy_units') or [])
    if raw_units:
        unit_ids = [str(unit.get('unit_id') or '') for unit in raw_units]
        spawn_ids = [str(unit.get('spawn_instance_id') or '') for unit in raw_units]
        if any(not unit_id for unit_id in unit_ids) or len(unit_ids) != len(set(unit_ids)):
            raise ValueError('terminal_unit_identity_mismatch')
        nonempty_spawn_ids = [spawn_id for spawn_id in spawn_ids if spawn_id]
        if len(nonempty_spawn_ids) != len(set(nonempty_spawn_ids)):
            raise ValueError('terminal_duplicate_spawn')
        if any(not bool(unit.get('dead')) or int(unit.get('hp', 1) or 0) > 0 for unit in raw_units):
            raise ValueError('terminal_living_unit')
    elif not bool(persisted_state.get('mob_dead')) or int(persisted_state.get('mob_hp', 1) or 0) > 0:
        raise ValueError('terminal_living_unit')
    if not bool(persisted_state.get('mob_dead')):
        raise ValueError('terminal_mob_alive')

    anchor_id = str(encounter.get('anchor_spawn_instance_id') or '')
    spawn_rows = conn.execute('''SELECT spawn_instance_id, location_id, mob_id, spawn_profile,
            special_spawn_key, state, linked_encounter_id
        FROM pve_spawn_instances WHERE linked_encounter_id=? ORDER BY spawn_instance_id''',
        (encounter_id,)).fetchall()
    if anchor_id:
        if not spawn_rows or anchor_id not in {str(row['spawn_instance_id']) for row in spawn_rows}:
            raise ValueError('terminal_anchor_provenance_mismatch')
        expected_spawn_ids = {str(row['spawn_instance_id']) for row in spawn_rows}
        actual_spawn_ids = {
            str(unit.get('spawn_instance_id') or '') for unit in raw_units
        } if raw_units else {str(persisted_state.get('anchor_spawn_instance_id') or '')}
        if actual_spawn_ids != expected_spawn_ids:
            raise ValueError('terminal_spawn_roster_mismatch')
        units_by_spawn = {str(unit.get('spawn_instance_id')): unit for unit in raw_units}
        for row in spawn_rows:
            if str(row['state']) != 'active' or str(row['linked_encounter_id']) != encounter_id:
                raise ValueError('terminal_spawn_state_mismatch')
            unit = units_by_spawn.get(str(row['spawn_instance_id'])) if raw_units else persisted_state
            if str(unit.get('mob_id') or encounter_mob_id) != str(row['mob_id']):
                raise ValueError('terminal_spawn_mob_mismatch')
            if str(unit.get('spawn_profile') or persisted_state.get('spawn_profile') or 'normal').lower() != str(row['spawn_profile']).lower():
                raise ValueError('terminal_spawn_profile_mismatch')
            if str(row['location_id']) != str(encounter.get('location_id') or ''):
                raise ValueError('terminal_spawn_location_mismatch')
            if str(unit.get('special_spawn_key') or '') != str(row['special_spawn_key'] or ''):
                raise ValueError('terminal_spawn_special_mismatch')
    elif any(str(unit.get('spawn_instance_id') or '') for unit in raw_units):
        raise ValueError('terminal_unproven_spawn')

    return persisted_state, persisted_mob


def _stable_units(battle_state: dict, fallback_mob: dict) -> list[dict]:
    raw_units = list(battle_state.get('enemy_units') or [])
    if not raw_units:
        raw_units = [{
            'unit_id': 'unit-1',
            'mob_id': battle_state.get('mob_id') or fallback_mob.get('id'),
            'spawn_profile': battle_state.get('spawn_profile', 'normal'),
            'special_spawn_key': battle_state.get('special_spawn_key'),
            'spawn_instance_id': battle_state.get('anchor_spawn_instance_id'),
        }]
    normalized = []
    for index, raw in enumerate(raw_units, start=1):
        unit = dict(raw)
        unit.setdefault('unit_id', f'unit-{index}')
        unit.setdefault('mob_id', battle_state.get('mob_id') or fallback_mob.get('id'))
        unit.setdefault('spawn_profile', battle_state.get('spawn_profile', 'normal'))
        normalized.append(unit)
    return sorted(normalized, key=lambda unit: (str(unit.get('unit_id') or ''), str(unit.get('spawn_instance_id') or '')))


def _roll_legacy_gear_spec(item_id: str, mob_level: int, rng: random.Random,
                           quality_floor: str | None = None) -> dict:
    from game.itemization import roll_generated_rarity

    item = get_item(item_id) or {}
    rarity = clamp_rarity_to_quality_floor(roll_generated_rarity(rng=rng), quality_floor)
    item_tier = determine_mob_drop_item_tier(mob_level=mob_level)
    rolls = generate_secondary_rolls_for_item(item, rarity=rarity, item_tier=item_tier, rng=rng)
    return {
        'base_item_id': item_id,
        'item_tier': item_tier,
        'rarity': rarity,
        'secondary_rolls': rolls,
        'enhance_level': 0,
        'durability': 100,
        'max_durability': 100,
        'guaranteed': False,
    }


def _roll_unit_rewards(*, unit: dict, fallback_mob: dict, route_id: str | None,
                       policy_version: str, dry_streak: int, rng: random.Random,
                       location_id: str) -> tuple[dict, int]:
    mob_id = str(unit.get('mob_id') or fallback_mob.get('id') or '')
    mob = dict(MOBS.get(mob_id) or fallback_mob)
    mob_level = max(1, int(mob.get('level', 1)))
    spawn_profile = str(unit.get('spawn_profile') or 'normal').lower()
    gold = rng.randint(int(mob.get('gold_min', 0)), int(mob.get('gold_max', 0)))
    non_gear: list[str] = []
    gear_specs: list[dict] = []

    source_metadata = build_open_world_combat_source_metadata(
        source_id=mob_id,
        mob_level=mob_level,
        source_category=mob.get('reward_source_category'),
        creature_taxonomy=mob.get('creature_taxonomy'),
        location_id=location_id,
        encounter_role=unit.get('encounter_role'),
        spawn_profile=spawn_profile,
        spawn_identity=str(unit.get('spawn_instance_id') or '') or None,
    )

    field_policy = (
        policy_version == FIELD_REWARD_POLICY_VERSION
        and route_id is not None
        and spawn_profile in GEAR_CHANCE_BY_SPAWN_PROFILE
    )
    for item_id, chance in mob.get('loot_table', ()):
        item = get_item(item_id) or {}
        if item.get('item_type') in {'weapon', 'armor', 'accessory'}:
            if not field_policy and rng.random() < float(chance):
                gear_specs.append(_roll_legacy_gear_spec(
                    item_id, mob_level, rng, source_metadata.quality_floor_rarity))
            continue
        if rng.random() < float(chance):
            reward_family = classify_item_reward_family(str(item_id))
            allowed = is_reward_family_allowed_for_source(source_metadata, reward_family)
            if reward_family == 'enhancement_material':
                routing = resolve_enhancement_material_routing(str(item_id), source_metadata.source_category)
                allowed = allowed and (routing is None or routing.is_allowed)
            if allowed:
                non_gear.append(str(item_id))

    counter_before = dry_streak
    guaranteed = False
    if field_policy:
        if rng.random() < GEAR_CHANCE_BY_SPAWN_PROFILE[spawn_profile]:
            item_id = choose_field_item(route_id, rng)
            rarity = choose_weighted_rarity(spawn_profile, rng)
            item_tier = min(FIELD_MAX_TIER, determine_mob_drop_item_tier(mob_level=mob_level))
            gear_specs.append({
                'base_item_id': item_id,
                'item_tier': item_tier,
                'rarity': rarity,
                'secondary_rolls': generate_secondary_rolls_for_item(
                    get_item(item_id) or {}, rarity=rarity, item_tier=item_tier, rng=rng),
                'enhance_level': 0,
                'durability': 100,
                'max_durability': 100,
                'guaranteed': False,
            })
            dry_streak = 0
        else:
            dry_streak += DRY_STREAK_INCREMENT_BY_SPAWN_PROFILE[spawn_profile]
            if dry_streak >= FIELD_DRY_STREAK_THRESHOLD:
                item_id = choose_field_item(route_id, rng)
                item_tier = min(FIELD_MAX_TIER, determine_mob_drop_item_tier(mob_level=mob_level))
                gear_specs.append({
                    'base_item_id': item_id,
                    'item_tier': item_tier,
                    'rarity': 'uncommon',
                    'secondary_rolls': generate_secondary_rolls_for_item(
                        get_item(item_id) or {}, rarity='uncommon', item_tier=item_tier, rng=rng),
                    'enhance_level': 0,
                    'durability': 100,
                    'max_durability': 100,
                    'guaranteed': True,
                })
                dry_streak = 0
                guaranteed = True
            else:
                dry_streak = min(FIELD_DRY_STREAK_THRESHOLD - 1, dry_streak)

    return ({
        'unit_id': str(unit.get('unit_id') or ''),
        'spawn_instance_id': str(unit.get('spawn_instance_id') or '') or None,
        'mob_id': mob_id,
        'mob_level': mob_level,
        'spawn_profile': spawn_profile,
        'special_spawn_key': str(unit.get('special_spawn_key') or '') or None,
        'exp': int(mob.get('exp_reward', 0)),
        'gold': gold,
        'non_gear': non_gear,
        'gear_specs': gear_specs,
        'counter_before': counter_before,
        'counter_after': dry_streak,
        'guaranteed': guaranteed,
        'source_metadata': asdict(source_metadata),
    }, dry_streak)


def build_reward_plan(*, conn, encounter: dict, battle_state: dict, fallback_mob: dict) -> dict:
    """Pure-result planner: all random outcomes become persisted concrete values."""
    encounter_id = str(encounter['encounter_id'])
    location_id = str(encounter.get('location_id') or battle_state.get('location_id') or '')
    route_id = resolve_progress_route_id(location_id)
    policy_version = str(encounter.get('reward_policy_version') or LEGACY_REWARD_POLICY_VERSION)
    if policy_version not in SUPPORTED_POLICY_VERSIONS:
        raise ValueError(f'unknown_reward_policy:{policy_version}')
    seed = str(encounter.get('reward_seed') or encounter_id)
    units = _stable_units(battle_state, fallback_mob)

    participant_ids, persisted_status = _locked_roster(conn, encounter)
    eligible = []
    defeated = []
    for player_id in participant_ids:
        snapshot = _participant_snapshot(battle_state, player_id)
        if persisted_status.get(player_id) != 'active' or not snapshot or (
            bool(snapshot.get('player_dead', snapshot.get('defeated', False)))
            or int(snapshot.get('player_hp', snapshot.get('hp', 0)) or 0) <= 0
        ):
            defeated.append(player_id)
        else:
            eligible.append(player_id)

    recipients = []
    for player_id in eligible:
        dry_streak = 0
        if route_id is not None:
            row = conn.execute('SELECT dry_streak FROM player_gear_progress WHERE player_id=? AND route_id=?',
                               (player_id, route_id)).fetchone()
            dry_streak = int(row['dry_streak']) if row else 0
        before = dry_streak
        unit_results = []
        for unit in units:
            unit_rng = random.Random(f'{seed}:{player_id}:{unit.get("unit_id")}')
            unit_result, dry_streak = _roll_unit_rewards(
                unit=unit,
                fallback_mob=fallback_mob,
                route_id=route_id,
                policy_version=policy_version,
                dry_streak=dry_streak,
                rng=unit_rng,
                location_id=location_id,
            )
            unit_results.append(unit_result)
        recipients.append({
            'player_id': player_id,
            'counter_before': before,
            'counter_after': dry_streak,
            'units': unit_results,
        })

    owner_player_id = int(encounter['owner_player_id'])
    owner_snapshot = _participant_snapshot(battle_state, owner_player_id)
    return {
        'schema_version': SETTLEMENT_SCHEMA_VERSION,
        'policy_version': policy_version,
        'encounter_id': encounter_id,
        'owner_player_id': int(encounter['owner_player_id']),
        'location_id': location_id,
        'route_id': route_id,
        'reward_seed': seed,
        'enemy_units': units,
        'eligible_recipient_ids': eligible,
        'defeated_participant_ids': defeated,
        'recipients': recipients,
        'owner_mastery': {
            'player_id': owner_player_id,
            'weapon_id': str(owner_snapshot.get('weapon_id') or 'unarmed'),
            # The historical +10 belongs to the encounter owner, but a
            # defeated owner is not an eligible victory-reward recipient.
            'exp': 10 if owner_player_id in eligible else 0,
        },
    }


def prepare_victory_settlement(*, encounter_id: str, battle_state: dict, mob: dict,
                               failure_hook: FailureHook | None = None) -> dict:
    """T1: persist terminal snapshot + deterministic plan + resolving state."""
    conn = get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        ensure_gear_progression_schema(conn)
        existing = conn.execute('SELECT * FROM pve_reward_settlements WHERE encounter_id=?', (encounter_id,)).fetchone()
        if existing:
            return {'status': str(existing['status']), 'plan': _load_json(existing['plan_json']),
                    'result': _load_json(existing['result_json'])}
        row = conn.execute('SELECT * FROM pve_encounters WHERE encounter_id=?', (encounter_id,)).fetchone()
        if not row:
            conn.rollback()
            return {'status': 'not_found'}
        encounter = dict(row)
        if encounter['status'] != 'active':
            conn.rollback()
            return {'status': 'not_active'}
        try:
            authoritative_state, authoritative_mob = _validate_terminal_snapshot(
                conn=conn,
                encounter=encounter,
                supplied_state=battle_state,
                supplied_mob=mob,
            )
        except ValueError as exc:
            conn.rollback()
            return {'status': 'invalid_outcome', 'reason': str(exc)}
        plan = build_reward_plan(
            conn=conn,
            encounter=encounter,
            battle_state=authoritative_state,
            fallback_mob=authoritative_mob,
        )
        conn.execute('''INSERT INTO pve_reward_settlements
            (encounter_id, schema_version, policy_version, status, plan_json)
            VALUES (?, ?, ?, 'prepared', ?)''',
            (encounter_id, SETTLEMENT_SCHEMA_VERSION, plan['policy_version'], _canonical_json(plan)))
        conn.execute('''UPDATE pve_encounters SET status='resolving_victory', battle_state_json=?,
            mob_json=?, updated_at=CURRENT_TIMESTAMP WHERE encounter_id=? AND status='active' ''',
            (_canonical_json(authoritative_state), _canonical_json(authoritative_mob), encounter_id))
        if failure_hook:
            failure_hook('before_t1_commit')
        conn.commit()
        if failure_hook:
            failure_hook('after_t1_commit')
        return {'status': 'prepared', 'plan': plan}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _apply_progression(conn, player_id: int, exp_gain: int, gold_gain: int,
                       failure_hook: FailureHook | None = None) -> dict:
    row = conn.execute('SELECT level, exp, gold, stat_points FROM players WHERE telegram_id=?', (player_id,)).fetchone()
    if not row:
        raise RuntimeError(f'settlement_player_missing:{player_id}')
    old_level = int(row['level'])
    level = old_level
    exp_value = int(row['exp']) + exp_gain
    while exp_value >= exp_to_next_level(level):
        exp_value -= exp_to_next_level(level)
        level += 1
    stat_points = int(row['stat_points']) + (level - old_level) * 3
    gold = int(row['gold']) + gold_gain
    conn.execute('UPDATE players SET level=?, exp=?, stat_points=? WHERE telegram_id=?',
                 (level, exp_value, stat_points, player_id))
    if failure_hook:
        failure_hook('after_xp_update')
    conn.execute('UPDATE players SET gold=? WHERE telegram_id=?', (gold, player_id))
    if failure_hook:
        failure_hook('after_gold_update')
    return {'level_before': old_level, 'level_after': level, 'exp_after': exp_value,
            'gold_after': gold, 'leveled_up': level > old_level}


def _stack_quantity(conn, player_id: int, item_id: str) -> int:
    row = conn.execute('SELECT COALESCE(SUM(quantity), 0) AS quantity FROM inventory '
                       'WHERE telegram_id=? AND item_id=?', (player_id, item_id)).fetchone()
    return int(row['quantity']) if row else 0


def _verify_gear_delivery(conn, *, player_id: int, instance_id: int, spec: dict,
                          encounter_id: str) -> None:
    row = conn.execute('SELECT * FROM gear_instances WHERE id=? AND telegram_id=?',
                       (instance_id, player_id)).fetchone()
    if not row:
        raise RuntimeError('gear_delivery_missing')
    actual = dict(row)
    try:
        actual_secondaries = json.loads(actual.get('secondary_rolls_json') or '[]')
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError('gear_delivery_invalid_secondaries') from exc
    expected = {
        'base_item_id': str(spec['base_item_id']),
        'item_tier': int(spec['item_tier']),
        'rarity': str(spec['rarity']),
        'enhance_level': int(spec.get('enhance_level', 0)),
        'durability': int(spec.get('durability', 100)),
        'max_durability': int(spec.get('max_durability', 100)),
        'source_settlement_id': encounter_id,
    }
    if any(actual.get(key) != value for key, value in expected.items()):
        raise RuntimeError('gear_delivery_spec_mismatch')
    if _canonical_json({'rolls': actual_secondaries}) != _canonical_json({'rolls': spec.get('secondary_rolls', [])}):
        raise RuntimeError('gear_delivery_secondary_mismatch')


def _has_other_live_engagement(conn, player_id: int, encounter_id: str) -> bool:
    from game.pvp_live import is_player_busy_with_live_pvp

    other_pve = conn.execute('''SELECT 1 FROM pve_encounter_participants p
        JOIN pve_encounters e ON e.encounter_id=p.encounter_id
        WHERE p.player_id=? AND p.status='active' AND e.encounter_id<>?
          AND e.status IN ('forming','active','resolving_victory') LIMIT 1''',
        (int(player_id), encounter_id)).fetchone()
    return bool(other_pve) or is_player_busy_with_live_pvp(int(player_id), conn=conn)


def apply_prepared_settlement(encounter_id: str, *, failure_hook: FailureHook | None = None) -> dict:
    """T2: atomically apply every economic/progression/finalization mutation."""
    from game.quest_board import register_hunt_kill_progress
    from game.weapon_mastery import add_mastery_exp

    conn = get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT * FROM pve_reward_settlements WHERE encounter_id=?', (encounter_id,)).fetchone()
        if not row:
            conn.rollback()
            return {'status': 'not_found'}
        if str(row['status']) == 'applied':
            return {'status': 'applied', 'result': _load_json(row['result_json']), 'already_applied': True}
        if str(row['status']) != 'prepared':
            conn.rollback()
            return {'status': str(row['status'])}
        if int(row['schema_version']) != SETTLEMENT_SCHEMA_VERSION or str(row['policy_version']) not in SUPPORTED_POLICY_VERSIONS:
            raise RuntimeError('unknown_settlement_version')
        plan = _load_json(row['plan_json'])
        if plan.get('encounter_id') != encounter_id:
            raise RuntimeError('settlement_identity_mismatch')
        encounter = conn.execute('SELECT status FROM pve_encounters WHERE encounter_id=?', (encounter_id,)).fetchone()
        if not encounter or str(encounter['status']) != 'resolving_victory':
            raise RuntimeError('settlement_encounter_state_mismatch')

        recipient_results = []
        for recipient_index, recipient in enumerate(plan.get('recipients', [])):
            player_id = int(recipient['player_id'])
            units = list(recipient.get('units') or [])
            exp_gain = sum(int(unit.get('exp', 0)) for unit in units)
            gold_gain = sum(int(unit.get('gold', 0)) for unit in units)
            progression = _apply_progression(conn, player_id, exp_gain, gold_gain, failure_hook)
            granted_stackables = []
            granted_gear = []
            for unit in units:
                for item_index, item_id in enumerate(unit.get('non_gear', [])):
                    metadata_payload = unit.get('source_metadata') or {}
                    source_metadata = RewardSourceMetadata(**metadata_payload) if metadata_payload else None
                    before_quantity = _stack_quantity(conn, player_id, str(item_id))
                    grant = grant_item_to_player(
                        player_id,
                        str(item_id),
                        quantity=1,
                        source='mob_drop',
                        source_level=int(unit.get('mob_level', 1)),
                        source_metadata=source_metadata,
                        conn=conn,
                    )
                    after_quantity = _stack_quantity(conn, player_id, str(item_id))
                    if (
                        int(grant.get('stackable_added', 0)) != 1
                        or int(grant.get('gear_instances_created', 0)) != 0
                        or after_quantity != before_quantity + 1
                    ):
                        raise RuntimeError('stackable_delivery_mismatch')
                    granted_stackables.append(str(item_id))
                    if failure_hook and item_index == 0:
                        failure_hook('after_first_stackable_grant')
                for gear_index, spec in enumerate(unit.get('gear_specs', [])):
                    metadata_payload = unit.get('source_metadata') or {}
                    source_metadata = RewardSourceMetadata(**metadata_payload) if metadata_payload else None
                    grant = grant_item_to_player(
                        player_id,
                        str(spec['base_item_id']),
                        quantity=1,
                        source='mob_drop',
                        source_level=int(unit.get('mob_level', 1)),
                        source_metadata=source_metadata,
                        gear_spec=spec,
                        source_settlement_id=encounter_id,
                        provenance={
                            'encounter_id': encounter_id,
                            'location_id': plan.get('location_id'),
                            'route_id': plan.get('route_id'),
                            'unit_id': unit.get('unit_id'),
                            'mob_id': unit.get('mob_id'),
                            'spawn_profile': unit.get('spawn_profile'),
                        },
                        conn=conn,
                    )
                    instance_ids = list(grant.get('instance_ids') or [])
                    if int(grant.get('gear_instances_created', 0)) != 1 or len(instance_ids) != 1:
                        raise RuntimeError('gear_delivery_mismatch')
                    instance_id = int(instance_ids[0])
                    _verify_gear_delivery(
                        conn,
                        player_id=player_id,
                        instance_id=instance_id,
                        spec=spec,
                        encounter_id=encounter_id,
                    )
                    granted_gear.append({**spec, 'instance_id': instance_id})
                    if failure_hook and gear_index == 0:
                        failure_hook('after_first_gear_instance')
                register_hunt_kill_progress(
                    player_id=player_id,
                    mob_id=str(unit.get('mob_id') or ''),
                    location_id=str(plan.get('location_id') or ''),
                    spawn_profile=str(unit.get('spawn_profile') or 'normal'),
                    special_spawn_key=unit.get('special_spawn_key'),
                    conn=conn,
                )
                if failure_hook:
                    failure_hook('after_contract_progress')
            route_id = plan.get('route_id')
            if route_id is not None:
                conn.execute('''INSERT INTO player_gear_progress(player_id, route_id, dry_streak, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP) ON CONFLICT(player_id, route_id) DO UPDATE SET
                    dry_streak=excluded.dry_streak, updated_at=CURRENT_TIMESTAMP''',
                    (player_id, route_id, int(recipient.get('counter_after', 0))))
                if failure_hook:
                    failure_hook('after_counter_update')
            if not _has_other_live_engagement(conn, player_id, encounter_id):
                conn.execute('DELETE FROM skill_cooldowns WHERE telegram_id=?', (player_id,))
            recipient_results.append({
                'player_id': player_id,
                'exp': exp_gain,
                'gold': gold_gain,
                'stackable_items': granted_stackables,
                'gear': granted_gear,
                'guaranteed': any(bool(spec.get('guaranteed')) for spec in granted_gear),
                **progression,
            })

        mastery = plan.get('owner_mastery') or {}
        mastery_exp = int(mastery.get('exp', 0))
        mastery_result = None
        if mastery_exp > 0:
            mastery_result = add_mastery_exp(
                int(mastery.get('player_id', plan.get('owner_player_id', 0))),
                str(mastery.get('weapon_id') or 'unarmed'),
                mastery_exp,
                conn=conn,
            )
        if failure_hook:
            failure_hook('after_mastery_award')

        if failure_hook:
            failure_hook('before_final_encounter_update')

        all_participant_ids = list(plan.get('eligible_recipient_ids') or []) + list(plan.get('defeated_participant_ids') or [])
        for player_id in all_participant_ids:
            if not _has_other_live_engagement(conn, int(player_id), encounter_id):
                conn.execute('UPDATE players SET in_battle=0 WHERE telegram_id=?', (int(player_id),))
        conn.execute("UPDATE pve_encounter_participants SET status='victory', updated_at=CURRENT_TIMESTAMP "
                     "WHERE encounter_id=? AND status='active'", (encounter_id,))
        conn.execute("UPDATE pve_encounters SET status='victory', updated_at=CURRENT_TIMESTAMP, "
                     "finished_at=CURRENT_TIMESTAMP WHERE encounter_id=? AND status='resolving_victory'", (encounter_id,))
        conn.execute("""UPDATE pve_spawn_instances SET state='respawning', linked_encounter_id=NULL,
            respawn_available_at=datetime('now', '+30 seconds'), updated_at=CURRENT_TIMESTAMP
            WHERE linked_encounter_id=?""", (encounter_id,))
        result = {
            'encounter_id': encounter_id,
            'location_id': plan.get('location_id'),
            'route_id': plan.get('route_id'),
            'recipients': recipient_results,
            'mastery': mastery_result,
            'applied_at': datetime.now(timezone.utc).isoformat(),
        }
        conn.execute('''UPDATE pve_reward_settlements SET status='applied', result_json=?,
            updated_at=CURRENT_TIMESTAMP, applied_at=CURRENT_TIMESTAMP WHERE encounter_id=? AND status='prepared' ''',
            (_canonical_json(result), encounter_id))
        conn.commit()
        if failure_hook:
            failure_hook('after_t2_commit')
        return {'status': 'applied', 'result': result, 'already_applied': False}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_settlement(encounter_id: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute('SELECT * FROM pve_reward_settlements WHERE encounter_id=?', (encounter_id,)).fetchone()
        if not row:
            return None
        return {**dict(row), 'plan': _load_json(row['plan_json']), 'result': _load_json(row['result_json'])}
    finally:
        conn.close()


def list_recent_reward_receipts(player_id: int, limit: int = 20) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute('''SELECT s.encounter_id, s.result_json, s.applied_at
            FROM pve_reward_settlements s
            JOIN pve_encounter_participants p ON p.encounter_id=s.encounter_id
            WHERE p.player_id=? AND s.status='applied' AND s.result_json IS NOT NULL
              AND EXISTS (
                  SELECT 1 FROM json_each(s.result_json, '$.recipients') recipient
                  WHERE CAST(json_extract(recipient.value, '$.player_id') AS INTEGER)=?
              )
            ORDER BY s.applied_at DESC, s.encounter_id DESC LIMIT ?''',
            (player_id, player_id, max(1, min(20, int(limit))))).fetchall()
    finally:
        conn.close()
    receipts = []
    for row in rows:
        result = _load_json(row['result_json'])
        recipient = next((r for r in result.get('recipients', []) if int(r.get('player_id', 0)) == player_id), None)
        if recipient:
            receipts.append({'encounter_id': row['encounter_id'], 'applied_at': row['applied_at'],
                             'location_id': result.get('location_id'), 'recipient': recipient})
    return receipts


def get_reward_receipt_for_player(player_id: int, encounter_id: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute('''SELECT s.encounter_id, s.result_json, s.applied_at
            FROM pve_reward_settlements s
            JOIN pve_encounter_participants p ON p.encounter_id=s.encounter_id
            WHERE p.player_id=? AND s.encounter_id=? AND s.status='applied'
              AND s.result_json IS NOT NULL LIMIT 1''', (player_id, encounter_id)).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    result = _load_json(row['result_json'])
    recipient = next(
        (value for value in result.get('recipients', []) if int(value.get('player_id', 0)) == player_id),
        None,
    )
    if not recipient:
        return None
    return {
        'encounter_id': str(row['encounter_id']),
        'applied_at': row['applied_at'],
        'location_id': result.get('location_id'),
        'recipient': recipient,
    }


def recover_prepared_settlements(limit: int = 20) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT encounter_id FROM pve_reward_settlements WHERE status='prepared' "
                            "ORDER BY created_at LIMIT ?", (max(1, min(100, int(limit))),)).fetchall()
    finally:
        conn.close()
    recovered = []
    for row in rows:
        encounter_id = str(row['encounter_id'])
        try:
            recovered.append(apply_prepared_settlement(encounter_id))
        except Exception:
            logger.exception('Prepared settlement recovery failed: encounter_id=%s', encounter_id)
            recovered.append({'status': 'retryable', 'encounter_id': encounter_id})
    return recovered


def recover_player_settlements(player_id: int, limit: int = 20) -> dict:
    """Bounded entry-point recovery plus owner-readable legacy-review evidence."""
    conn = get_connection()
    try:
        rows = conn.execute('''SELECT DISTINCT s.encounter_id, s.status
            FROM pve_reward_settlements s
            JOIN pve_encounter_participants p ON p.encounter_id=s.encounter_id
            WHERE p.player_id=? AND s.status IN ('prepared','legacy_review')
            ORDER BY s.updated_at LIMIT ?''',
            (player_id, max(1, min(20, int(limit))))).fetchall()
    finally:
        conn.close()
    recovered = []
    pending = []
    legacy_review = []
    for row in rows:
        if str(row['status']) == 'prepared':
            encounter_id = str(row['encounter_id'])
            try:
                result = apply_prepared_settlement(encounter_id)
                if result.get('status') == 'applied':
                    recovered.append(result)
                else:
                    pending.append(encounter_id)
            except Exception:
                logger.exception('Player settlement recovery failed: player_id=%s encounter_id=%s', player_id, encounter_id)
                pending.append(encounter_id)
        else:
            legacy_review.append(str(row['encounter_id']))
    return {'recovered': recovered, 'pending': pending, 'legacy_review': legacy_review}


def list_legacy_review_reports(player_id: int, limit: int = 20) -> list[dict]:
    """Return bounded, owner-readable evidence without authorizing compensation."""
    conn = get_connection()
    try:
        rows = conn.execute('''SELECT s.encounter_id, s.plan_json, s.created_at
            FROM pve_reward_settlements s
            JOIN pve_encounter_participants p ON p.encounter_id=s.encounter_id
            WHERE p.player_id=? AND s.status='legacy_review'
            ORDER BY s.created_at DESC LIMIT ?''',
            (player_id, max(1, min(20, int(limit))))).fetchall()
    finally:
        conn.close()
    reports = []
    for row in rows:
        plan = _load_json(row['plan_json'])
        evidence = plan.get('legacy_evidence') or {}
        battle = evidence.get('battle_state') or {}
        units = list(battle.get('enemy_units') or [])
        mob_ids = sorted({str(unit.get('mob_id')) for unit in units if unit.get('mob_id')})
        if not mob_ids and (battle.get('mob_id') or evidence.get('mob_id')):
            mob_ids = [str(battle.get('mob_id') or evidence.get('mob_id'))]
        reports.append({
            'encounter_id': str(row['encounter_id']),
            'reason': str(plan.get('reason') or 'ambiguous_pre_v1_resolving_victory'),
            'location_id': str(evidence.get('location_id') or battle.get('location_id') or ''),
            'mob_ids': mob_ids,
            'created_at': row['created_at'],
            'evidence': evidence,
            'automatic_replay': False,
            'compensation_requires_owner_decision': True,
        })
    return reports


def review_ambiguous_legacy_victories() -> int:
    """Quarantine old resolving victories whose reward history cannot be proven."""
    conn = get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        ensure_gear_progression_schema(conn)
        rows = conn.execute('''SELECT * FROM pve_encounters e WHERE e.status='resolving_victory'
            AND NOT EXISTS (SELECT 1 FROM pve_reward_settlements s WHERE s.encounter_id=e.encounter_id)''').fetchall()
        count = 0
        for row in rows:
            evidence = {key: row[key] for key in row.keys() if key not in {'battle_state_json', 'mob_json'}}
            evidence['battle_state'] = _load_json(row['battle_state_json'])
            evidence['mob'] = _load_json(row['mob_json'])
            plan = {'schema_version': SETTLEMENT_SCHEMA_VERSION, 'legacy_evidence': evidence,
                    'reason': 'ambiguous_pre_v1_resolving_victory'}
            conn.execute('''INSERT INTO pve_reward_settlements
                (encounter_id, schema_version, policy_version, status, plan_json)
                VALUES (?, ?, ?, 'legacy_review', ?)''',
                (row['encounter_id'], SETTLEMENT_SCHEMA_VERSION, LEGACY_REWARD_POLICY_VERSION, _canonical_json(plan)))
            conn.execute("UPDATE pve_encounters SET status='legacy_review', updated_at=CURRENT_TIMESTAMP, "
                         "finished_at=CURRENT_TIMESTAMP WHERE encounter_id=?", (row['encounter_id'],))
            participants = conn.execute('SELECT player_id FROM pve_encounter_participants WHERE encounter_id=?',
                                        (row['encounter_id'],)).fetchall()
            conn.execute("UPDATE pve_encounter_participants SET status='legacy_review', updated_at=CURRENT_TIMESTAMP "
                         "WHERE encounter_id=?", (row['encounter_id'],))
            for participant in participants:
                player_id = int(participant['player_id'])
                if not _has_other_live_engagement(conn, player_id, str(row['encounter_id'])):
                    conn.execute('UPDATE players SET in_battle=0 WHERE telegram_id=?', (player_id,))
            count += 1
        conn.commit()
        return count
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
