"""Phase 8: tier advancement foundation + minimal runtime for gear instances.

Scope intentionally narrow:
- gear-instance-first advancement path;
- preserve instance identity, rarity, and enhance level;
- rarity-based cost escalation;
- no unique-specific advancement mechanics (explicitly excluded).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from database import get_connection
from game.gear_instances import MAX_GENERATED_TIER, ORDINARY_GENERATED_RARITIES, is_gear_item
from game.items_data import get_item

AdvancementStatus = Literal[
    'advanced',
    'instance_not_found',
    'not_eligible',
    'invalid_target_tier',
    'max_tier',
    'player_not_found',
    'no_gold',
    'no_material',
]

RARITY_ADVANCEMENT_MULTIPLIER = {
    'common': 1.0,
    'uncommon': 1.6,
    'rare': 3.5,
    'epic': 7.5,
    'legendary': 15.0,
}

TARGET_TIER_BASE_GOLD_COST = {
    5: 120,
    10: 260,
    15: 520,
    20: 950,
    25: 1500,
    30: 2300,
    35: 3400,
    40: 5000,
    45: 7400,
    50: 10500,
}


@dataclass(frozen=True)
class AdvancementRequest:
    telegram_id: int
    instance_id: int
    target_tier: int | None = None


@dataclass(frozen=True)
class AdvancementCost:
    gold: int
    material_id: str
    material_qty: int


@dataclass(frozen=True)
class AdvancementResult:
    status: AdvancementStatus
    instance_id: int
    previous_tier: int | None = None
    new_tier: int | None = None
    target_tier: int | None = None
    cost: AdvancementCost | None = None
    rarity_preserved: str | None = None
    enhance_level_preserved: int | None = None
    base_item_id_preserved: str | None = None

    @property
    def is_success(self) -> bool:
        return self.status == 'advanced'


def resolve_next_tier(current_tier: int) -> int | None:
    normalized = max(1, int(current_tier))
    if normalized >= MAX_GENERATED_TIER:
        return None
    if normalized < 5:
        return 5
    return min(MAX_GENERATED_TIER, normalized + 5)


def resolve_advancement_cost(*, current_tier: int, target_tier: int, rarity: str) -> AdvancementCost:
    normalized_target = max(5, min(MAX_GENERATED_TIER, int(target_tier)))
    base_gold = TARGET_TIER_BASE_GOLD_COST.get(normalized_target, TARGET_TIER_BASE_GOLD_COST[MAX_GENERATED_TIER])
    rarity_multiplier = RARITY_ADVANCEMENT_MULTIPLIER.get(rarity, 1.0)
    gold_cost = max(1, int(round(base_gold * rarity_multiplier)))

    if normalized_target <= 20:
        material_id = 'enhancement_crystal'
    elif normalized_target <= 35:
        material_id = 'power_essence'
    else:
        material_id = 'ashen_core'

    step_qty = max(1, (normalized_target - max(1, int(current_tier))) // 5)
    material_qty = max(1, int(round(step_qty * max(1.0, rarity_multiplier / 2.5))))
    return AdvancementCost(gold=gold_cost, material_id=material_id, material_qty=material_qty)


def is_instance_eligible_for_tier_advancement(instance_row: dict) -> bool:
    base_item_id = str(instance_row.get('base_item_id') or '')
    rarity = str(instance_row.get('rarity') or '')
    base_item = get_item(base_item_id)

    if not is_gear_item(base_item):
        return False
    if rarity == 'unique':
        return False
    return rarity in ORDINARY_GENERATED_RARITIES


def advance_gear_instance_tier(request: AdvancementRequest) -> AdvancementResult:
    conn = get_connection()
    try:
        row = conn.execute(
            'SELECT id, telegram_id, base_item_id, item_tier, rarity, enhance_level FROM gear_instances WHERE telegram_id=? AND id=?',
            (request.telegram_id, request.instance_id),
        ).fetchone()
        if row is None:
            return AdvancementResult(status='instance_not_found', instance_id=request.instance_id)

        instance = dict(row)
        if not is_instance_eligible_for_tier_advancement(instance):
            return AdvancementResult(status='not_eligible', instance_id=request.instance_id)

        current_tier = max(1, int(instance.get('item_tier', 1)))
        next_tier = resolve_next_tier(current_tier)
        if next_tier is None:
            return AdvancementResult(status='max_tier', instance_id=request.instance_id, previous_tier=current_tier)

        target_tier = next_tier if request.target_tier is None else int(request.target_tier)
        if target_tier != next_tier:
            return AdvancementResult(
                status='invalid_target_tier',
                instance_id=request.instance_id,
                previous_tier=current_tier,
                target_tier=target_tier,
            )

        rarity = str(instance.get('rarity') or 'common')
        cost = resolve_advancement_cost(current_tier=current_tier, target_tier=target_tier, rarity=rarity)

        player = conn.execute('SELECT gold FROM players WHERE telegram_id=?', (request.telegram_id,)).fetchone()
        if not player:
            return AdvancementResult(status='player_not_found', instance_id=request.instance_id)

        current_gold = int(player['gold'])
        if current_gold < cost.gold:
            return AdvancementResult(
                status='no_gold',
                instance_id=request.instance_id,
                previous_tier=current_tier,
                target_tier=target_tier,
                cost=cost,
            )

        material_row = conn.execute(
            'SELECT id, quantity FROM inventory WHERE telegram_id=? AND item_id=?',
            (request.telegram_id, cost.material_id),
        ).fetchone()
        current_material = int(material_row['quantity']) if material_row else 0
        if current_material < cost.material_qty:
            return AdvancementResult(
                status='no_material',
                instance_id=request.instance_id,
                previous_tier=current_tier,
                target_tier=target_tier,
                cost=cost,
            )

        conn.execute('BEGIN')
        conn.execute('UPDATE players SET gold=? WHERE telegram_id=?', (current_gold - cost.gold, request.telegram_id))
        new_material_qty = current_material - cost.material_qty
        if new_material_qty > 0:
            conn.execute('UPDATE inventory SET quantity=? WHERE id=?', (new_material_qty, material_row['id']))
        else:
            conn.execute('DELETE FROM inventory WHERE id=?', (material_row['id'],))
        conn.execute(
            'UPDATE gear_instances SET item_tier=? WHERE telegram_id=? AND id=?',
            (target_tier, request.telegram_id, request.instance_id),
        )
        conn.commit()

        return AdvancementResult(
            status='advanced',
            instance_id=request.instance_id,
            previous_tier=current_tier,
            new_tier=target_tier,
            target_tier=target_tier,
            cost=cost,
            rarity_preserved=rarity,
            enhance_level_preserved=int(instance.get('enhance_level') or 0),
            base_item_id_preserved=str(instance.get('base_item_id') or ''),
        )
    finally:
        conn.close()
