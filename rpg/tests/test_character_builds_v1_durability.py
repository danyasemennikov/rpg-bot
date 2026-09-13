from __future__ import annotations

from datetime import datetime, timedelta, timezone

from database import get_connection
from game.build_contract import RULES_VERSION
from game.build_progression import ensure_build_schema
from game.combat_orders import consume_combat_intent, issue_combat_intents, load_combat_orders
from game.pve_reward_settlement import _v1_mastery_awards


def test_mastery_awards_only_manual_survivors_with_frozen_family_and_caps_at_80():
    state = {
        "participant_states_v1": {
            "1": {"family": "bow", "level": 10, "manual_contribution": True},
            "2": {"family": "wand", "level": 10, "manual_contribution": False},
            "3": {"family": "unarmed", "level": 10, "manual_contribution": True},
        }
    }
    units = [
        {"unit_id": "a", "mob_level": 10, "spawn_profile": "normal"},
        {"unit_id": "b", "mob_level": 10, "spawn_profile": "elite"},
        {"unit_id": "c", "mob_level": 1, "spawn_profile": "rare"},
        {"unit_id": "d", "mob_level": 10, "spawn_profile": "normal"},
    ]
    assert _v1_mastery_awards(battle_state=state, eligible=[1, 2, 3], units=units) == [{
        "player_id": 1,
        "weapon_id": "bow",
        "exp": 80,
        "units": [
            {"unit_id": "a", "mob_level": 10, "spawn_profile": "normal", "exp": 20},
            {"unit_id": "b", "mob_level": 10, "spawn_profile": "elite", "exp": 40},
            {"unit_id": "c", "mob_level": 1, "spawn_profile": "rare", "exp": 10},
            {"unit_id": "d", "mob_level": 10, "spawn_profile": "normal", "exp": 20},
        ],
    }]


def test_pve_ui_intent_is_single_use_deadline_bound_and_durable():
    conn = get_connection()
    ensure_build_schema(conn)
    conn.execute(
        """INSERT INTO pve_encounters
        (encounter_id, owner_player_id, status, mob_id, battle_state_json, mob_json,
         source_units_json, rules_version, turn_revision)
        VALUES ('intent-v1', 1, 'active', 'rat', '{}', '{}', '[]', ?, 0)""",
        (RULES_VERSION,),
    )
    conn.execute(
        "INSERT INTO pve_encounter_participants (encounter_id, player_id, status) VALUES ('intent-v1', 1, 'active')"
    )
    conn.commit()
    conn.close()

    deadline = (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat()
    action = {"kind": "normal", "target_info": {"id": "enemy-1"}}
    token = issue_combat_intents(
        1, encounter_id="intent-v1", turn_revision=1,
        deadline_at=deadline, actions=[action],
    )[__import__("json").dumps(action, ensure_ascii=False, sort_keys=True, separators=(",", ":"))]
    assert consume_combat_intent(1, token)["accepted"] is True
    assert consume_combat_intent(1, token) == {"accepted": False, "reason": "stale_action"}
    orders = load_combat_orders(encounter_kind="pve", encounter_id="intent-v1", turn_revision=1)
    assert len(orders) == 1
    assert orders[0]["action"] == action

