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


def select_all_enemies_in_small_pack(targets, active_unit_id=None):
    living = _living_targets(targets)
    return _active_first_order(living, active_unit_id)


def select_front_line_cluster(targets, active_unit_id=None, cap=4):
    living = _living_targets(targets)
    by_line = {line: [] for line in FORMATION_LINES}
    for target in living:
        line = normalize_formation_line(target.get('formation_line'))
        if line:
            by_line[line].append(target)

    selected_line = None
    for line in FORMATION_LINES:
        if by_line[line]:
            selected_line = line
            break
    if selected_line is None:
        return []

    selected = by_line[selected_line]
    ordered = _active_first_order(selected, active_unit_id)
    safe_cap = max(0, int(cap or 0))
    return ordered[:safe_cap]


def select_back_line_single(targets, active_unit_id=None):
    living = _living_targets(targets)
    if not living:
        return []

    back_order = (
        FORMATION_LINE_SUPPORT,
        FORMATION_LINE_RANGED,
        FORMATION_LINE_MELEE,
        FORMATION_LINE_FRONT,
    )
    by_line = {line: [] for line in back_order}
    for target in living:
        line = normalize_formation_line(target.get('formation_line'))
        if line in by_line:
            by_line[line].append(target)

    selected_line = None
    for line in back_order:
        if by_line[line]:
            selected_line = line
            break
    if selected_line is None:
        return []

    ordered = _active_first_order(by_line[selected_line], active_unit_id)
    return ordered[:1]
