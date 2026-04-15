from __future__ import annotations

from dataclasses import dataclass

from database import get_connection
from game.balance import exp_to_next_level
from game.i18n import get_mob_name, t


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


HUNT_CONTRACTS: tuple[HuntContract, ...] = (
    HuntContract(
        contract_key='hunt_forest_wolves',
        title_i18n_key='location.quest_contract_wolves_title',
        target_mob_id='forest_wolf',
        required_kills=5,
        reward_exp=70,
        reward_gold=30,
        board_locations=('village',),
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


def _normalize_spawn_profile(raw_profile: object) -> str:
    value = str(raw_profile or '').strip().lower()
    if value in {'elite', 'rare'}:
        return value
    return 'normal'


def list_hunt_contracts_for_location(location_id: str) -> list[HuntContract]:
    location = str(location_id or '').strip()
    return [contract for contract in HUNT_CONTRACTS if location in contract.board_locations]


def get_hunt_contract(contract_key: str) -> HuntContract | None:
    return HUNT_CONTRACTS_BY_KEY.get(str(contract_key or '').strip())


def get_player_hunt_contract_state(player_id: int) -> dict | None:
    _ensure_player_hunt_contract_table()
    conn = get_connection()
    row = conn.execute(
        '''
        SELECT player_id, contract_key, progress_kills, status, completed_at, claimed_at
        FROM player_hunt_contracts
        WHERE player_id=?
        LIMIT 1
        ''',
        (int(player_id),),
    ).fetchone()
    conn.close()
    if not row:
        return None
    state = dict(row)
    contract = get_hunt_contract(str(state.get('contract_key') or ''))
    if not contract:
        return None
    state['contract'] = contract
    return state


def accept_hunt_contract(*, player_id: int, location_id: str, contract_key: str) -> tuple[bool, str]:
    _ensure_player_hunt_contract_table()
    contract = get_hunt_contract(contract_key)
    if not contract:
        return False, 'not_found'
    if str(location_id) not in contract.board_locations:
        return False, 'wrong_board'

    current = get_player_hunt_contract_state(player_id)
    if current and current.get('status') in {'active', 'completed'}:
        return False, 'already_active'

    conn = get_connection()
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
    conn.close()
    return True, 'accepted'


def register_hunt_kill_progress(
    *,
    player_id: int,
    mob_id: str,
    spawn_profile: str | None = None,
    special_spawn_key: str | None = None,
) -> dict:
    _ensure_player_hunt_contract_table()
    state = get_player_hunt_contract_state(player_id)
    if not state or state.get('status') != 'active':
        return {'updated': False, 'completed_now': False}

    contract: HuntContract = state['contract']
    if str(mob_id or '') != contract.target_mob_id:
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

    conn = get_connection()
    conn.execute(
        '''
        UPDATE player_hunt_contracts
        SET progress_kills=?, status=?, completed_at=CASE WHEN ?='completed' THEN CURRENT_TIMESTAMP ELSE completed_at END, updated_at=CURRENT_TIMESTAMP
        WHERE player_id=?
        ''',
        (next_progress, next_status, next_status, int(player_id)),
    )
    conn.commit()
    conn.close()
    return {
        'updated': next_progress != current_progress,
        'completed_now': completed_now,
        'progress_kills': next_progress,
        'required_kills': contract.required_kills,
    }


def claim_completed_hunt_contract(*, player_id: int, location_id: str) -> tuple[bool, str, dict | None]:
    _ensure_player_hunt_contract_table()
    state = get_player_hunt_contract_state(player_id)
    if not state:
        return False, 'no_contract', None
    if state.get('status') == 'claimed':
        return False, 'already_claimed', None
    if state.get('status') != 'completed':
        return False, 'not_completed', None

    contract: HuntContract = state['contract']
    if str(location_id) not in contract.board_locations:
        return False, 'wrong_board', None

    conn = get_connection()
    player = conn.execute(
        'SELECT level, exp, gold, stat_points FROM players WHERE telegram_id=?',
        (int(player_id),),
    ).fetchone()
    if not player:
        conn.close()
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

    conn.execute(
        '''
        UPDATE players
        SET exp=?, gold=?, level=?, stat_points=?
        WHERE telegram_id=?
        ''',
        (exp_value, gold_value, level, stat_points, int(player_id)),
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
    conn.close()

    return True, 'claimed', {
        'contract': contract,
        'reward_exp': reward_exp,
        'reward_gold': reward_gold,
        'leveled_up': leveled_up,
        'new_level': level,
    }


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
    return t(
        'location.quest_contract_row',
        lang,
        title=build_contract_title(contract, lang),
        target=_build_contract_target_line(contract, lang),
        kills=contract.required_kills,
        exp=contract.reward_exp,
        gold=contract.reward_gold,
    )
