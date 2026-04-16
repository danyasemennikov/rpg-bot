from __future__ import annotations

from dataclasses import dataclass
import logging

from database import get_connection
from game.balance import exp_to_next_level
from game.gear_instances import grant_item_to_player
from game.i18n import get_item_name, get_location_name, get_mob_name, t

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HuntContract:
    contract_key: str
    title_i18n_key: str
    target_mob_id: str
    required_kills: int
    reward_exp: int
    reward_gold: int
    board_locations: tuple[str, ...]
    spawn_profile: str | None = None
    special_spawn_key: str | None = None
    bonus_item_id: str | None = None
    bonus_item_qty: int = 1
    hunter_points_reward: int = 20
    required_hunter_rank: str | None = None
    target_location_ids: tuple[str, ...] = ()


HUNTER_RANK_THRESHOLDS: tuple[tuple[str, int], ...] = (
    ('novice', 0),
    ('tracker', 40),
    ('hunter', 100),
    ('slayer', 180),
    ('veteran', 280),
)
HUNTER_RANK_ORDER = {rank_key: idx for idx, (rank_key, _min_points) in enumerate(HUNTER_RANK_THRESHOLDS)}


HUNT_CONTRACTS: tuple[HuntContract, ...] = (
    HuntContract(
        contract_key='hunt_forest_wolves',
        title_i18n_key='location.quest_contract_wolves_title',
        target_mob_id='forest_wolf',
        required_kills=5,
        reward_exp=70,
        reward_gold=30,
        board_locations=('village',),
        hunter_points_reward=20,
        target_location_ids=('dark_forest',),
    ),
    HuntContract(
        contract_key='hunt_elite_boars',
        title_i18n_key='location.quest_contract_elite_boars_title',
        target_mob_id='forest_boar',
        required_kills=2,
        reward_exp=90,
        reward_gold=45,
        board_locations=('village',),
        spawn_profile='elite',
        hunter_points_reward=30,
        required_hunter_rank='tracker',
        target_location_ids=('dark_forest',),
    ),
    HuntContract(
        contract_key='hunt_greyfang',
        title_i18n_key='location.quest_contract_greyfang_title',
        target_mob_id='forest_wolf',
        required_kills=1,
        reward_exp=120,
        reward_gold=70,
        board_locations=('village',),
        special_spawn_key='greyfang',
        bonus_item_id='wolf_fang',
        bonus_item_qty=2,
        hunter_points_reward=45,
        target_location_ids=('dark_forest',),
    ),
    HuntContract(
        contract_key='hunt_forest_spiders',
        title_i18n_key='location.quest_contract_spiders_title',
        target_mob_id='forest_spider',
        required_kills=4,
        reward_exp=85,
        reward_gold=40,
        board_locations=('village',),
        hunter_points_reward=20,
        target_location_ids=('dark_forest',),
    ),
    HuntContract(
        contract_key='hunt_mine_goblins',
        title_i18n_key='location.quest_contract_mine_goblins_title',
        target_mob_id='goblin_miner',
        required_kills=3,
        reward_exp=110,
        reward_gold=55,
        board_locations=('frontier_outpost',),
        hunter_points_reward=35,
        required_hunter_rank='hunter',
        target_location_ids=('old_mines',),
    ),
    HuntContract(
        contract_key='hunt_amber_golem',
        title_i18n_key='location.quest_contract_amber_golem_title',
        target_mob_id='stone_golem',
        required_kills=1,
        reward_exp=140,
        reward_gold=80,
        board_locations=('frontier_outpost',),
        spawn_profile='elite',
        bonus_item_id='enhancement_crystal',
        hunter_points_reward=60,
        required_hunter_rank='veteran',
        target_location_ids=('old_mines',),
    ),
    HuntContract(
        contract_key='hunt_mine_rats',
        title_i18n_key='location.quest_contract_mine_rats_title',
        target_mob_id='mine_rat',
        required_kills=5,
        reward_exp=95,
        reward_gold=46,
        board_locations=('frontier_outpost',),
        hunter_points_reward=25,
        required_hunter_rank='tracker',
        target_location_ids=('old_mines',),
    ),
    HuntContract(
        contract_key='hunt_cave_bats',
        title_i18n_key='location.quest_contract_cave_bats_title',
        target_mob_id='cave_bat',
        required_kills=4,
        reward_exp=105,
        reward_gold=50,
        board_locations=('frontier_outpost',),
        hunter_points_reward=30,
        required_hunter_rank='hunter',
        target_location_ids=('old_mines',),
    ),
)

HUNT_CONTRACTS_BY_KEY = {contract.contract_key: contract for contract in HUNT_CONTRACTS}


def _ensure_player_hunt_contract_table() -> None:
    conn = get_connection()
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS player_hunt_contracts (
            player_id       INTEGER PRIMARY KEY,
            contract_key    TEXT NOT NULL,
            progress_kills  INTEGER NOT NULL DEFAULT 0,
            status          TEXT NOT NULL DEFAULT 'active',
            completed_at    TIMESTAMP,
            claimed_at      TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
    )
    conn.commit()
    conn.close()


def _ensure_player_hunter_progress_table(conn=None) -> None:
    should_close = conn is None
    if conn is None:
        conn = get_connection()
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS player_hunter_progress (
            player_id       INTEGER PRIMARY KEY,
            hunter_points   INTEGER NOT NULL DEFAULT 0,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
    )
    if should_close:
        conn.commit()
        conn.close()


def _normalize_spawn_profile(raw_profile: object) -> str:
    value = str(raw_profile or '').strip().lower()
    if value in {'elite', 'rare'}:
        return value
    return 'normal'


def _table_exists(conn, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (str(table_name),),
    ).fetchone()
    return bool(row)


def resolve_hunter_rank(hunter_points: int) -> str:
    points = max(0, int(hunter_points))
    current = HUNTER_RANK_THRESHOLDS[0][0]
    for rank_key, min_points in HUNTER_RANK_THRESHOLDS:
        if points >= min_points:
            current = rank_key
        else:
            break
    return current


def get_next_hunter_rank_progress(hunter_points: int) -> dict:
    points = max(0, int(hunter_points))
    current_rank = resolve_hunter_rank(points)
    current_idx = HUNTER_RANK_ORDER[current_rank]
    current_floor = HUNTER_RANK_THRESHOLDS[current_idx][1]

    next_rank = None
    points_to_next = 0
    current_span_total = 0
    current_span_progress = points - current_floor

    if current_idx + 1 < len(HUNTER_RANK_THRESHOLDS):
        next_rank, next_threshold = HUNTER_RANK_THRESHOLDS[current_idx + 1]
        points_to_next = max(0, next_threshold - points)
        current_span_total = max(0, next_threshold - current_floor)

    return {
        'hunter_points': points,
        'current_rank': current_rank,
        'next_rank': next_rank,
        'points_to_next': points_to_next,
        'current_span_progress': max(0, current_span_progress),
        'current_span_total': current_span_total,
    }


def _get_player_hunter_progress_with_conn(conn, player_id: int) -> dict:
    points = 0
    if _table_exists(conn, 'player_hunter_progress'):
        row = conn.execute(
            'SELECT hunter_points FROM player_hunter_progress WHERE player_id=? LIMIT 1',
            (int(player_id),),
        ).fetchone()
        if row:
            points = max(0, int(row['hunter_points'] or 0))
    progress = get_next_hunter_rank_progress(points)
    progress['rank_i18n_key'] = f"location.hunter_rank_{progress['current_rank']}"
    return progress


def get_player_hunter_progress(player_id: int) -> dict:
    conn = get_connection()
    try:
        return _get_player_hunter_progress_with_conn(conn, player_id)
    finally:
        conn.close()


def _grant_hunter_points_with_conn(conn, *, player_id: int, points_gained: int) -> dict:
    points_delta = max(0, int(points_gained))
    before = _get_player_hunter_progress_with_conn(conn, player_id)
    before_points = int(before['hunter_points'])
    after_points = before_points + points_delta
    conn.execute(
        '''
        INSERT INTO player_hunter_progress (player_id, hunter_points, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(player_id) DO UPDATE SET
            hunter_points=excluded.hunter_points,
            updated_at=CURRENT_TIMESTAMP
        ''',
        (int(player_id), after_points),
    )
    after = get_next_hunter_rank_progress(after_points)
    rank_up = HUNTER_RANK_ORDER[after['current_rank']] > HUNTER_RANK_ORDER[before['current_rank']]
    after['rank_i18n_key'] = f"location.hunter_rank_{after['current_rank']}"
    return {
        'points_before': before_points,
        'points_gained': points_delta,
        'points_after': after_points,
        'rank_before': before['current_rank'],
        'rank_after': after['current_rank'],
        'rank_up': rank_up,
        'progress': after,
    }


def list_hunt_contracts_for_location(location_id: str) -> list[HuntContract]:
    location = str(location_id or '').strip()
    return [contract for contract in HUNT_CONTRACTS if location in contract.board_locations]


def get_hunt_contract(contract_key: str) -> HuntContract | None:
    return HUNT_CONTRACTS_BY_KEY.get(str(contract_key or '').strip())


def _is_hunter_rank_requirement_met(*, hunter_rank: str, required_rank: str | None) -> bool:
    if not required_rank:
        return True
    if required_rank not in HUNTER_RANK_ORDER:
        return True
    current_idx = HUNTER_RANK_ORDER.get(hunter_rank, 0)
    required_idx = HUNTER_RANK_ORDER[required_rank]
    return current_idx >= required_idx


def get_contract_rank_lock_reason(*, contract: HuntContract, player_hunter_rank: str, lang: str) -> str | None:
    required_rank = str(contract.required_hunter_rank or '').strip().lower()
    if not required_rank:
        return None
    if _is_hunter_rank_requirement_met(hunter_rank=player_hunter_rank, required_rank=required_rank):
        return None
    return t('location.quest_board_locked_reason_rank', lang, rank=t(f'location.hunter_rank_{required_rank}', lang))


def list_hunt_contracts_for_player(*, location_id: str, player_id: int, lang: str) -> dict:
    progress = get_player_hunter_progress(player_id)
    current_rank = str(progress['current_rank'])
    available: list[HuntContract] = []
    locked: list[dict] = []
    for contract in list_hunt_contracts_for_location(location_id):
        locked_reason = get_contract_rank_lock_reason(contract=contract, player_hunter_rank=current_rank, lang=lang)
        if locked_reason:
            locked.append({'contract': contract, 'reason': locked_reason})
        else:
            available.append(contract)
    return {
        'available': available,
        'locked': locked,
        'hunter_progress': progress,
    }


def _get_player_hunt_contract_state_with_conn(conn, player_id: int) -> dict | None:
    if not _table_exists(conn, 'player_hunt_contracts'):
        return None
    row = conn.execute(
        '''
        SELECT player_id, contract_key, progress_kills, status, completed_at, claimed_at
        FROM player_hunt_contracts
        WHERE player_id=?
        LIMIT 1
        ''',
        (int(player_id),),
    ).fetchone()
    if not row:
        return None
    state = dict(row)
    contract = get_hunt_contract(str(state.get('contract_key') or ''))
    if not contract:
        return None
    state['contract'] = contract
    return state


def get_player_hunt_contract_state(player_id: int) -> dict | None:
    conn = get_connection()
    try:
        return _get_player_hunt_contract_state_with_conn(conn, player_id)
    finally:
        conn.close()


def accept_hunt_contract(*, player_id: int, location_id: str, contract_key: str) -> tuple[bool, str]:
    _ensure_player_hunt_contract_table()
    contract = get_hunt_contract(contract_key)
    if not contract:
        return False, 'not_found'
    if str(location_id) not in contract.board_locations:
        return False, 'wrong_board'
    conn = get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        current = _get_player_hunt_contract_state_with_conn(conn, player_id)
        if current and current.get('status') in {'active', 'completed'}:
            conn.rollback()
            return False, 'already_active'

        player_progress = _get_player_hunter_progress_with_conn(conn, player_id)
        if not _is_hunter_rank_requirement_met(
            hunter_rank=str(player_progress['current_rank']),
            required_rank=contract.required_hunter_rank,
        ):
            conn.rollback()
            return False, 'rank_locked'

        conn.execute(
            '''
            INSERT INTO player_hunt_contracts (player_id, contract_key, progress_kills, status, completed_at, claimed_at, updated_at)
            VALUES (?, ?, 0, 'active', NULL, NULL, CURRENT_TIMESTAMP)
            ON CONFLICT(player_id) DO UPDATE SET
                contract_key=excluded.contract_key,
                progress_kills=0,
                status='active',
                completed_at=NULL,
                claimed_at=NULL,
                updated_at=CURRENT_TIMESTAMP
            ''',
            (int(player_id), contract.contract_key),
        )
        conn.commit()
        return True, 'accepted'
    finally:
        conn.close()


def register_hunt_kill_progress(
    *,
    player_id: int,
    mob_id: str,
    location_id: str | None = None,
    spawn_profile: str | None = None,
    special_spawn_key: str | None = None,
) -> dict:
    conn = get_connection()
    try:
        state = _get_player_hunt_contract_state_with_conn(conn, player_id)
        if not state or state.get('status') != 'active':
            return {'updated': False, 'completed_now': False}

        contract: HuntContract = state['contract']
        if str(mob_id or '') != contract.target_mob_id:
            return {'updated': False, 'completed_now': False}

        kill_location_id = str(location_id or '').strip()
        if contract.target_location_ids and kill_location_id not in contract.target_location_ids:
            return {'updated': False, 'completed_now': False}

        actual_profile = _normalize_spawn_profile(spawn_profile)
        if contract.spawn_profile and actual_profile != _normalize_spawn_profile(contract.spawn_profile):
            return {'updated': False, 'completed_now': False}

        actual_special_key = str(special_spawn_key or '').strip().lower()
        required_special_key = str(contract.special_spawn_key or '').strip().lower()
        if required_special_key and actual_special_key != required_special_key:
            return {'updated': False, 'completed_now': False}

        current_progress = int(state.get('progress_kills', 0) or 0)
        next_progress = min(contract.required_kills, current_progress + 1)
        completed_now = next_progress >= contract.required_kills and current_progress < contract.required_kills
        next_status = 'completed' if next_progress >= contract.required_kills else 'active'

        conn.execute(
            '''
            UPDATE player_hunt_contracts
            SET progress_kills=?, status=?, completed_at=CASE WHEN ?='completed' THEN CURRENT_TIMESTAMP ELSE completed_at END, updated_at=CURRENT_TIMESTAMP
            WHERE player_id=?
            ''',
            (next_progress, next_status, next_status, int(player_id)),
        )
        conn.commit()
        return {
            'updated': next_progress != current_progress,
            'completed_now': completed_now,
            'progress_kills': next_progress,
            'required_kills': contract.required_kills,
        }
    finally:
        conn.close()


def claim_completed_hunt_contract(*, player_id: int, location_id: str) -> tuple[bool, str, dict | None]:
    _ensure_player_hunt_contract_table()
    conn = get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        _ensure_player_hunter_progress_table(conn)
        state = _get_player_hunt_contract_state_with_conn(conn, player_id)
        if not state:
            conn.rollback()
            return False, 'no_contract', None
        if state.get('status') == 'claimed':
            conn.rollback()
            return False, 'already_claimed', None
        if state.get('status') != 'completed':
            conn.rollback()
            return False, 'not_completed', None

        contract: HuntContract = state['contract']
        if str(location_id) not in contract.board_locations:
            conn.rollback()
            return False, 'wrong_board', None

        player = conn.execute(
            'SELECT level, exp, gold, stat_points FROM players WHERE telegram_id=?',
            (int(player_id),),
        ).fetchone()
        if not player:
            conn.rollback()
            return False, 'player_not_found', None

        level = int(player['level'])
        exp_value = int(player['exp'])
        reward_exp = int(contract.reward_exp)
        reward_gold = int(contract.reward_gold)
        exp_value += reward_exp
        leveled_up = False
        while exp_value >= exp_to_next_level(level):
            exp_value -= exp_to_next_level(level)
            level += 1
            leveled_up = True
        levels_gained = max(0, level - int(player['level']))
        stat_points = int(player['stat_points']) + (levels_gained * 3)
        gold_value = int(player['gold']) + reward_gold

        bonus_item_result = None
        conn.execute(
            '''
            UPDATE players
            SET exp=?, gold=?, level=?, stat_points=?
            WHERE telegram_id=?
            ''',
            (exp_value, gold_value, level, stat_points, int(player_id)),
        )

        if contract.bonus_item_id:
            bonus_qty = max(1, int(contract.bonus_item_qty))
            grant_result = grant_item_to_player(
                int(player_id),
                contract.bonus_item_id,
                quantity=bonus_qty,
                source='quest_contract_reward',
                source_level=level,
                conn=conn,
            )
            delivered_qty = int(grant_result.get('stackable_added', 0)) + int(grant_result.get('gear_instances_created', 0))
            if delivered_qty < bonus_qty:
                logger.warning(
                    'Hunt claim bonus item delivery mismatch: player_id=%s contract=%s item=%s expected_qty=%s delivered_qty=%s',
                    int(player_id),
                    contract.contract_key,
                    contract.bonus_item_id,
                    bonus_qty,
                    delivered_qty,
                )
                raise RuntimeError('bonus_item_reward_not_delivered')
            bonus_item_result = {
                'item_id': contract.bonus_item_id,
                'quantity': bonus_qty,
                'grant_result': grant_result,
                'granted': True,
            }

        hunter_progress = _grant_hunter_points_with_conn(
            conn,
            player_id=int(player_id),
            points_gained=int(contract.hunter_points_reward),
        )

        conn.execute(
            '''
            UPDATE player_hunt_contracts
            SET status='claimed', claimed_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
            WHERE player_id=?
            ''',
            (int(player_id),),
        )
        conn.commit()
        return True, 'claimed', {
            'contract': contract,
            'reward_exp': reward_exp,
            'reward_gold': reward_gold,
            'leveled_up': leveled_up,
            'new_level': level,
            'bonus_item': bonus_item_result,
            'hunter_progress': hunter_progress,
        }
    except Exception:
        conn.rollback()
        logger.exception(
            'Hunt claim transaction failed: player_id=%s location_id=%s',
            int(player_id),
            str(location_id),
        )
        return False, 'reward_delivery_failed', None
    finally:
        conn.close()


def abandon_hunt_contract(*, player_id: int) -> tuple[bool, str]:
    _ensure_player_hunt_contract_table()
    conn = get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        state = _get_player_hunt_contract_state_with_conn(conn, player_id)
        if not state:
            conn.rollback()
            return False, 'no_contract'
        if state.get('status') == 'completed':
            conn.rollback()
            return False, 'completed_must_claim'
        if state.get('status') != 'active':
            conn.rollback()
            return False, 'not_active'

        conn.execute(
            '''
            DELETE FROM player_hunt_contracts
            WHERE player_id=?
            ''',
            (int(player_id),),
        )
        conn.commit()
        return True, 'abandoned'
    finally:
        conn.close()


def _contract_target_location_names(contract: HuntContract, lang: str) -> list[str]:
    names: list[str] = []
    for location_id in contract.target_location_ids:
        normalized_id = str(location_id or '').strip()
        if not normalized_id:
            continue
        names.append(get_location_name(normalized_id, lang))
    return names


def _build_contract_location_line(contract: HuntContract, lang: str) -> str:
    location_names = _contract_target_location_names(contract, lang)
    if not location_names:
        return t('location.quest_contract_location_any', lang)
    return ' / '.join(location_names)


def _build_contract_board_locations_line(contract: HuntContract, lang: str) -> str:
    board_names: list[str] = []
    for board_location_id in contract.board_locations:
        normalized_id = str(board_location_id or '').strip()
        if not normalized_id:
            continue
        board_names.append(get_location_name(normalized_id, lang))
    if not board_names:
        return t('location.quest_board_label_unknown', lang)
    return ' / '.join(board_names)


def build_contract_board_locations_line(contract: HuntContract, lang: str) -> str:
    return _build_contract_board_locations_line(contract, lang)


def _build_contract_location_hint(*, contract: HuntContract, lang: str, current_location_id: str | None = None) -> str:
    location_names = _contract_target_location_names(contract, lang)
    if not location_names:
        return t('location.quest_contract_hint_any', lang)

    current_location = str(current_location_id or '').strip()
    if current_location and current_location in contract.target_location_ids:
        return t('location.quest_contract_hint_here', lang)

    if len(location_names) == 1:
        return t('location.quest_contract_hint_target', lang, target=location_names[0])
    return t('location.quest_contract_hint_targets', lang, targets=' / '.join(location_names))


def _build_contract_target_line(contract: HuntContract, lang: str) -> str:
    mob_name = get_mob_name(contract.target_mob_id, lang)
    requirement_chunks = [mob_name]
    if contract.spawn_profile:
        if _normalize_spawn_profile(contract.spawn_profile) == 'elite':
            requirement_chunks.append(t('location.quest_contract_filter_elite', lang))
        elif _normalize_spawn_profile(contract.spawn_profile) == 'rare':
            requirement_chunks.append(t('location.quest_contract_filter_rare', lang))
    if contract.special_spawn_key:
        requirement_chunks.append(t('location.quest_contract_filter_special', lang, spawn_key=contract.special_spawn_key))
    return ', '.join(requirement_chunks)


def build_contract_title(contract: HuntContract, lang: str) -> str:
    return t(contract.title_i18n_key, lang)


def build_contract_row(contract: HuntContract, lang: str) -> str:
    bonus_reward = ''
    if contract.bonus_item_id:
        bonus_reward = t(
            'location.quest_contract_bonus_item',
            lang,
            qty=max(1, int(contract.bonus_item_qty)),
            item=get_item_name(contract.bonus_item_id, lang),
        )
    return t(
        'location.quest_contract_row',
        lang,
        title=build_contract_title(contract, lang),
        target=_build_contract_target_line(contract, lang),
        board_hint=_build_contract_board_locations_line(contract, lang),
        location_hint=_build_contract_location_line(contract, lang),
        kills=contract.required_kills,
        exp=contract.reward_exp,
        gold=contract.reward_gold,
        bonus=bonus_reward,
        hunter_points=max(0, int(contract.hunter_points_reward)),
    )


def build_hunt_contract_progress_line(*, player_id: int, lang: str, current_location_id: str | None = None) -> str | None:
    state = get_player_hunt_contract_state(player_id)
    if not state or state.get('status') not in {'active', 'completed'}:
        return None
    contract: HuntContract = state['contract']
    status_key = 'location.quest_board_status_ready' if state.get('status') == 'completed' else 'location.quest_board_status_active'
    return t(
        'location.location_active_contract_line',
        lang,
        title=build_contract_title(contract, lang),
        progress=int(state.get('progress_kills', 0) or 0),
        required=int(contract.required_kills),
        status=t(status_key, lang),
        geography_hint=_build_contract_location_hint(
            contract=contract,
            lang=lang,
            current_location_id=current_location_id,
        ),
    )
