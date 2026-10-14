"""P/XP/registration writer. The caller owns the SQLite writer transaction."""
import json
import time
from game.action_receipts import ActionRejected
from game.profession_progression import POLICY_VERSION, apply_profession_xp, profession_tier
from game.profession_schema import CRAFTING_PROFESSION_KEYS, GATHERING_PROFESSION_KEYS

PROFESSIONS = CRAFTING_PROFESSION_KEYS + GATHERING_PROFESSION_KEYS


def storage(profession):
    if profession in CRAFTING_PROFESSION_KEYS:
        return 'player_crafting_professions', 'player_id'
    if profession in GATHERING_PROFESSION_KEYS:
        return 'player_gathering_professions', 'telegram_id'
    raise ActionRejected('unknown_profession')


def get_state(conn, player_id, profession, *, registered=False):
    table, column = storage(profession)
    row = conn.execute(f'SELECT * FROM {table} WHERE {column}=? AND profession_key=?',
                       (player_id, profession)).fetchone()
    if not row or registered and row['registered_at'] is None:
        raise ActionRejected('profession_not_registered')
    return {**dict(row), 'tier': profession_tier(row['level'])}


def register_profession(conn, player_id, profession, *, now_ms=None):
    from game.action_receipts import peaceful_player
    from game.profession_schema import ensure_profession_rows
    if not conn.in_transaction:
        raise RuntimeError('profession registration requires writer transaction')
    peaceful_player(conn, player_id, service='craftsmen_guild')
    ensure_profession_rows(conn, player_id)
    state = get_state(conn, player_id, profession)
    if state['registered_at'] is not None:
        return state
    table, column = storage(profession)
    now_ms = int(time.time() * 1000) if now_ms is None else now_ms
    conn.execute(f'UPDATE {table} SET registered_at=?,revision=revision+1 WHERE {column}=? AND profession_key=?',
                 (now_ms, player_id, profession))
    for slot in range(1, 3 if profession in CRAFTING_PROFESSION_KEYS else 2):
        conn.execute('INSERT INTO profession_vouchers(player_id,profession_key,slot) VALUES (?,?,?)',
                     (player_id, profession, slot))
    return get_state(conn, player_id, profession)


def write_progression(conn, player_id, profession, result):
    if not conn.in_transaction:
        raise RuntimeError('profession XP requires writer transaction')
    table, column = storage(profession)
    changed = conn.execute(f'''UPDATE {table} SET level=?,exp=?,revision=revision+1
        WHERE {column}=? AND profession_key=? AND level=? AND exp=?''',
        (result.new_level, result.new_exp, player_id, profession, result.old_level, result.old_exp))
    if changed.rowcount != 1:
        raise ActionRejected('profession_state_changed')


def award_operation(conn, player_id, profession, *, operation_id, mode, source_id, attempted,
                    context_id=None, result=None, now_ms=None):
    if not conn.in_transaction:
        raise RuntimeError('profession operation requires writer transaction')
    if not operation_id or mode not in ('personal', 'paid_job', 'personal_processing', 'profession_exam'):
        raise ActionRejected('invalid_profession_operation')
    prior = conn.execute('SELECT * FROM profession_operation_receipts WHERE operation_id=?', (operation_id,)).fetchone()
    if prior:
        if (prior['player_id'], prior['profession_key'], prior['origin_mode'], prior['source_id'], prior['context_id']) != (
                player_id, profession, mode, source_id, context_id):
            raise ActionRejected('operation_identity_mismatch')
        return json.loads(prior['result_json'])
    state = get_state(conn, player_id, profession, registered=True)
    progression = apply_profession_xp(state['level'], state['exp'], attempted)
    write_progression(conn, player_id, profession, progression)
    outcome = {**(result or {}), 'profession_key': profession, **progression.__dict__}
    conn.execute('''INSERT INTO profession_operation_receipts
        (operation_id,player_id,profession_key,origin_mode,source_id,context_id,
         attempted,applied,discarded,policy_version,result_json,committed_ms)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
        (operation_id, player_id, profession, mode, source_id, context_id,
         progression.attempted, progression.applied, progression.discarded, POLICY_VERSION,
         json.dumps(outcome, sort_keys=True), int(time.time() * 1000) if now_ms is None else now_ms))
    return outcome
