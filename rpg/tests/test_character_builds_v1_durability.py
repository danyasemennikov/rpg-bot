from __future__ import annotations

from datetime import datetime, timedelta, timezone

from database import get_connection
from game.build_contract import RULES_VERSION
from game.build_progression import ensure_build_schema
from game.build_progression import migrate_character_builds_v1
from game.combat_orders import consume_combat_intent, issue_combat_intents, load_combat_orders
from game.pve_reward_settlement import _v1_mastery_awards
from game.pvp_live import (
    _LIVE_PVP_RUNTIME_STORE,
    _deserialize_reason_context,
    _ensure_live_runtime_for_battle,
    _init_live_battle_payload,
    _write_engagement_state,
    create_live_engagement,
    issue_manual_pvp_action_labels,
    resolve_live_battle_turn,
)


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


def test_v1_pvp_uses_opaque_durable_order_and_recovers_it_after_runtime_loss():
    migrate_character_builds_v1()
    attacker = 1
    defender = 777
    conn = get_connection()
    attacker_row = dict(conn.execute("SELECT * FROM players WHERE telegram_id=?", (attacker,)).fetchone())
    defender_row = dict(conn.execute("SELECT * FROM players WHERE telegram_id=?", (defender,)).fetchone())
    conn.close()
    engagement_id = create_live_engagement(
        attacker=attacker_row, defender=defender_row,
        location_id="capital_city", illegal_aggression=False,
    )
    conn = get_connection()
    row = conn.execute("SELECT * FROM pvp_engagements WHERE id=?", (engagement_id,)).fetchone()
    conn.close()
    battle = _init_live_battle_payload(
        attacker_id=attacker, defender_id=defender, now=datetime.now(timezone.utc),
    )
    _ensure_live_runtime_for_battle(engagement_row=row, battle=battle)
    initial_attacker_mana = battle["participants_v1"][str(attacker)]["mana"]
    payload = {"flow": "open_world_1v1", "battle": battle}
    _write_engagement_state(engagement_id=engagement_id, state="converted_to_battle", payload=payload)

    actions = issue_manual_pvp_action_labels(
        engagement_id=engagement_id, player_id=attacker, lang="en", battle=battle,
        attacker_id=attacker, defender_id=defender,
    )
    assert len(actions) == 3  # normal, Guard, universal Power Strike
    normal_token = actions[0][0]
    consumed = consume_combat_intent(attacker, normal_token)
    assert consumed["accepted"] is True
    assert consumed["encounter_kind"] == "pvp"

    # Simulate a process crash after the atomic order insert but before the
    # in-memory runtime receives/resolves that order.
    _LIVE_PVP_RUNTIME_STORE.reset()
    conn = get_connection()
    row = conn.execute("SELECT * FROM pvp_engagements WHERE id=?", (engagement_id,)).fetchone()
    conn.close()
    status, result_payload = resolve_live_battle_turn(
        row, actor_id=attacker, selected_action_id=None,
    )
    assert status == "resolved"
    assert result_payload["battle"]["turn_owner"] == defender
    assert result_payload["battle"]["participants_v1"][str(attacker)]["mana"] > initial_attacker_mana
    conn = get_connection()
    result = conn.execute(
        "SELECT result_json FROM combat_turn_results_v1 WHERE encounter_kind='pvp' AND encounter_id=?",
        (str(engagement_id),),
    ).fetchone()
    persisted = conn.execute("SELECT reason_context FROM pvp_engagements WHERE id=?", (engagement_id,)).fetchone()
    conn.close()
    assert result is not None
    assert _deserialize_reason_context(persisted["reason_context"])["battle"]["turn_owner"] == defender
