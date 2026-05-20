"""Combat formation and target-shape foundation helpers."""

FORMATION_LINE_FRONT = 'front'
FORMATION_LINE_MELEE = 'melee'
FORMATION_LINE_RANGED = 'ranged'
FORMATION_LINE_SUPPORT = 'support'

FORMATION_LINES = (
    FORMATION_LINE_FRONT,
    FORMATION_LINE_MELEE,
    FORMATION_LINE_RANGED,
    FORMATION_LINE_SUPPORT,
)

FORMATION_LINE_ICONS = {
    FORMATION_LINE_FRONT: '🛡️',
    FORMATION_LINE_MELEE: '⚔️',
    FORMATION_LINE_RANGED: '🏹',
    FORMATION_LINE_SUPPORT: '✨',
}

TARGET_SHAPE_SINGLE_ACTIVE_ENEMY = 'single_active_enemy'
TARGET_SHAPE_ALL_ENEMIES_IN_SMALL_PACK = 'all_enemies_in_small_pack'
TARGET_SHAPE_FRONT_LINE_CLUSTER = 'front_line_cluster'
TARGET_SHAPE_BACK_LINE_SINGLE = 'back_line_single'

TARGET_SHAPES = (
    TARGET_SHAPE_SINGLE_ACTIVE_ENEMY,
    TARGET_SHAPE_ALL_ENEMIES_IN_SMALL_PACK,
    TARGET_SHAPE_FRONT_LINE_CLUSTER,
    TARGET_SHAPE_BACK_LINE_SINGLE,
)

TARGET_PATTERN_ORDINARY_SINGLE_ENEMY = 'ordinary_single_enemy'
TARGET_PATTERN_ALL_ENEMIES_IN_SMALL_PACK = 'all_enemies_in_small_pack'
TARGET_PATTERN_FRONT_LINE_CLUSTER = 'front_line_cluster'
TARGET_PATTERN_BACK_LINE_SINGLE = 'back_line_single'
TARGET_PATTERN_TWO_FRONT_LINES_2X2 = 'two_front_lines_2x2'
TARGET_PATTERN_RANGED_LINE_SINGLE = 'ranged_line_single'

TARGET_PATTERN_IDS = (
    TARGET_PATTERN_ORDINARY_SINGLE_ENEMY,
    TARGET_PATTERN_ALL_ENEMIES_IN_SMALL_PACK,
    TARGET_PATTERN_FRONT_LINE_CLUSTER,
    TARGET_PATTERN_BACK_LINE_SINGLE,
    TARGET_PATTERN_TWO_FRONT_LINES_2X2,
    TARGET_PATTERN_RANGED_LINE_SINGLE,
)

TARGET_PATTERNS = {
    TARGET_PATTERN_ORDINARY_SINGLE_ENEMY: {
        'id': TARGET_PATTERN_ORDINARY_SINGLE_ENEMY,
        'kind': 'single',
        'line_selection': 'active_then_frontmost_occupied',
        'total_cap': 1,
        'execution_mode': 'single',
    },
    TARGET_PATTERN_ALL_ENEMIES_IN_SMALL_PACK: {
        'id': TARGET_PATTERN_ALL_ENEMIES_IN_SMALL_PACK,
        'kind': 'all_targets',
        'line_selection': 'all_living',
        'active_priority': 'within_selected_lines',
        'execution_mode': 'fanout',
    },
    TARGET_PATTERN_FRONT_LINE_CLUSTER: {
        'id': TARGET_PATTERN_FRONT_LINE_CLUSTER,
        'kind': 'line_window',
        'line_selection': 'frontmost_occupied',
        'line_count': 1,
        'per_line_cap': 4,
        'total_cap': 4,
        'active_priority': 'within_selected_lines',
        'execution_mode': 'fanout',
    },
    TARGET_PATTERN_BACK_LINE_SINGLE: {
        'id': TARGET_PATTERN_BACK_LINE_SINGLE,
        'kind': 'line_window',
        'line_selection': 'backmost_occupied',
        'line_count': 1,
        'per_line_cap': 1,
        'total_cap': 1,
        'active_priority': 'within_selected_lines',
        'execution_mode': 'single_redirect',
    },
    TARGET_PATTERN_TWO_FRONT_LINES_2X2: {
        'id': TARGET_PATTERN_TWO_FRONT_LINES_2X2,
        'kind': 'line_window',
        'line_selection': 'frontmost_occupied',
        'line_count': 2,
        'per_line_cap': 2,
        'total_cap': 4,
        'active_priority': 'within_selected_lines',
        'execution_mode': 'fanout',
    },
    TARGET_PATTERN_RANGED_LINE_SINGLE: {
        'id': TARGET_PATTERN_RANGED_LINE_SINGLE,
        'kind': 'line_window',
        'line_selection': 'specific_lines',
        'target_lines': [FORMATION_LINE_RANGED],
        'line_count': 1,
        'per_line_cap': 1,
        'total_cap': 1,
        'active_priority': 'within_selected_lines',
        'empty_policy': 'return_none',
        'execution_mode': 'single_redirect',
    },
}

TARGET_SHAPE_TO_PATTERN_ID = {
    TARGET_SHAPE_SINGLE_ACTIVE_ENEMY: TARGET_PATTERN_ORDINARY_SINGLE_ENEMY,
    TARGET_SHAPE_ALL_ENEMIES_IN_SMALL_PACK: TARGET_PATTERN_ALL_ENEMIES_IN_SMALL_PACK,
    TARGET_SHAPE_FRONT_LINE_CLUSTER: TARGET_PATTERN_FRONT_LINE_CLUSTER,
    TARGET_SHAPE_BACK_LINE_SINGLE: TARGET_PATTERN_BACK_LINE_SINGLE,
}


def normalize_formation_line(value):
    if value is None:
        return None
    line = str(value).strip().lower()
    if line in FORMATION_LINES:
        return line
    return None


def is_valid_formation_line(value):
    return normalize_formation_line(value) is not None


def resolve_default_player_formation_line(*, formation_line=None, weapon_profile=None, offhand_profile=None):
    explicit_line = normalize_formation_line(formation_line)
    if explicit_line:
        return explicit_line

    if str(offhand_profile or '').strip().lower() == 'shield':
        return FORMATION_LINE_FRONT

    normalized_weapon_profile = str(weapon_profile or '').strip().lower()
    if normalized_weapon_profile in {'holy_staff', 'holy_rod', 'tome'}:
        return FORMATION_LINE_SUPPORT
    if normalized_weapon_profile in {'bow', 'wand', 'magic_staff'}:
        return FORMATION_LINE_RANGED
    return FORMATION_LINE_MELEE


def resolve_default_enemy_formation_line(*, formation_line=None):
    explicit_line = normalize_formation_line(formation_line)
    if explicit_line:
        return explicit_line
    return FORMATION_LINE_MELEE


def _living_targets(targets):
    return [target for target in list(targets or []) if not bool(target.get('dead'))]


def _active_first_order(targets, active_unit_id):
    if not active_unit_id:
        return list(targets)
    active_id = str(active_unit_id)
    active = [target for target in targets if str(target.get('unit_id')) == active_id]
    if not active:
        return list(targets)
    rest = [target for target in targets if str(target.get('unit_id')) != active_id]
    return active + rest


def _group_living_targets_by_line(targets, line_order):
    by_line = {line: [] for line in line_order}
    for target in _living_targets(targets):
        line = normalize_formation_line(target.get('formation_line'))
        if line in by_line:
            by_line[line].append(target)
    return by_line


def _ordered_selected_lines(pattern):
    line_selection = pattern.get('line_selection')
    if line_selection == 'frontmost_occupied':
        return list(FORMATION_LINES)
    if line_selection == 'backmost_occupied':
        return [FORMATION_LINE_SUPPORT, FORMATION_LINE_RANGED, FORMATION_LINE_MELEE, FORMATION_LINE_FRONT]
    if line_selection == 'specific_lines':
        return [line for line in pattern.get('target_lines', []) if line in FORMATION_LINES]
    return []


def get_target_pattern(pattern_id=None):
    if not pattern_id:
        return None
    return TARGET_PATTERNS.get(str(pattern_id))


def resolve_target_pattern_id(skill_def_or_metadata=None):
    metadata = dict(skill_def_or_metadata or {})

    explicit_pattern_id = metadata.get('target_pattern_id')
    if explicit_pattern_id is not None:
        normalized = str(explicit_pattern_id)
        if normalized in TARGET_PATTERNS:
            return normalized
        return None

    target_shape = metadata.get('target_shape')
    if target_shape is not None:
        mapped = TARGET_SHAPE_TO_PATTERN_ID.get(str(target_shape))
        if mapped in TARGET_PATTERNS:
            return mapped

    return TARGET_PATTERN_ORDINARY_SINGLE_ENEMY


def select_targets_for_pattern(targets, pattern_id_or_pattern, active_unit_id=None):
    pattern = pattern_id_or_pattern
    if isinstance(pattern_id_or_pattern, str):
        pattern = get_target_pattern(pattern_id_or_pattern)
    if not pattern:
        return []

    pattern_id = pattern.get('id')
    living = _living_targets(targets)

    if pattern_id == TARGET_PATTERN_ORDINARY_SINGLE_ENEMY:
        active_first = _active_first_order(living, active_unit_id)
        if active_first and active_unit_id and str(active_first[0].get('unit_id')) == str(active_unit_id):
            return active_first[:1]

        by_line = _group_living_targets_by_line(living, FORMATION_LINES)
        for line in FORMATION_LINES:
            if by_line[line]:
                return [by_line[line][0]]
        return []

    if pattern_id == TARGET_PATTERN_ALL_ENEMIES_IN_SMALL_PACK:
        return _active_first_order(living, active_unit_id)

    if pattern_id in {
        TARGET_PATTERN_FRONT_LINE_CLUSTER,
        TARGET_PATTERN_BACK_LINE_SINGLE,
        TARGET_PATTERN_TWO_FRONT_LINES_2X2,
        TARGET_PATTERN_RANGED_LINE_SINGLE,
    }:
        line_order = _ordered_selected_lines(pattern)
        by_line = _group_living_targets_by_line(targets, line_order)
        selected_lines = []
        line_count = int(pattern.get('line_count') or 0)
        for line in line_order:
            if by_line[line]:
                selected_lines.append(line)
            if len(selected_lines) >= line_count:
                break

        if not selected_lines:
            return []

        selected_targets = []
        per_line_cap = int(pattern.get('per_line_cap') or 0)
        for line in selected_lines:
            ordered_line_targets = _active_first_order(by_line[line], active_unit_id)
            selected_targets.extend(ordered_line_targets[:per_line_cap])

        total_cap = int(pattern.get('total_cap') or 0)
        return selected_targets[:total_cap]

    return []


def select_all_enemies_in_small_pack(targets, active_unit_id=None):
    return select_targets_for_pattern(targets, TARGET_PATTERN_ALL_ENEMIES_IN_SMALL_PACK, active_unit_id=active_unit_id)


def select_front_line_cluster(targets, active_unit_id=None, cap=4):
    safe_cap = max(0, int(cap or 0))
    pattern = dict(TARGET_PATTERNS[TARGET_PATTERN_FRONT_LINE_CLUSTER])
    pattern['per_line_cap'] = safe_cap
    pattern['total_cap'] = safe_cap
    return select_targets_for_pattern(targets, pattern, active_unit_id=active_unit_id)


def select_back_line_single(targets, active_unit_id=None):
    return select_targets_for_pattern(targets, TARGET_PATTERN_BACK_LINE_SINGLE, active_unit_id=active_unit_id)[:1]
