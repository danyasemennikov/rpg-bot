"""Permanent recipe knowledge and deterministic guild learning."""

from __future__ import annotations

from database import get_connection
from game.action_receipts import ActionRejected, consume_action, peaceful_player
from game.economy_actions import find_receipt, intent_hash, store_business_rejection, store_receipt
from game.profession_recipes import get_recipe, parse_recipe_intent
from game.profession_schema import ensure_profession_rows


def known_recipe_ids(player_id: int, *, conn=None) -> tuple[str, ...]:
    owns = conn is None
    if owns:
        conn = get_connection()
    try:
        return tuple(row['recipe_id'] for row in conn.execute(
            'SELECT recipe_id FROM player_recipe_knowledge WHERE player_id=? ORDER BY recipe_id', (player_id,)
        ))
    finally:
        if owns:
            conn.close()


def learn_recipe(player_id: int, recipe_id: str, *, action_token: str, request_id: str | None = None) -> dict:
    request_id = request_id or f'ui:{action_token}'
    expected_hash = intent_hash('learn', player_id, {'recipe_id': recipe_id})
    conn = get_connection()
    authorized = False
    try:
        conn.execute('BEGIN IMMEDIATE')
        recovered = find_receipt(conn, player_id, request_id, 'learn', expected_hash)
        if recovered is not None:
            conn.commit()
            return recovered
        token_recipe = parse_recipe_intent(consume_action(conn, player_id, 'learn', action_token))
        if token_recipe != recipe_id:
            raise ActionRejected('stale_action')
        authorized = True
        recipe = get_recipe(recipe_id)
        if recipe is None:
            raise ActionRejected('recipe_not_found')
        player = peaceful_player(conn, player_id, service='craftsmen_guild')
        ensure_profession_rows(conn, player_id)
        known = conn.execute('SELECT 1 FROM player_recipe_knowledge WHERE player_id=? AND recipe_id=?',
                             (player_id, recipe_id)).fetchone()
        if known:
            result = {'schema_version': 1, 'action_kind': 'learn', 'status': 'already_known',
                      'player_id': player_id, 'location_id': player['location_id'], 'recipe_id': recipe_id,
                      'consumed': [], 'granted': [], 'gold_delta': 0, 'gold_after': player['gold'],
                      'progression': [], 'source': {'catalog_version': 1}, 'details': {}}
        else:
            state = conn.execute('SELECT level FROM player_crafting_professions WHERE player_id=? AND profession_key=?',
                                 (player_id, recipe.profession_key)).fetchone()
            if not state or state['level'] < recipe.required_level:
                raise ActionRejected('profession_level_too_low')
            if player['gold'] < recipe.learning_gold:
                raise ActionRejected('insufficient_gold')
            changed = conn.execute('UPDATE players SET gold=gold-? WHERE telegram_id=? AND gold>=?',
                                   (recipe.learning_gold, player_id, recipe.learning_gold))
            if changed.rowcount != 1:
                raise ActionRejected('insufficient_gold')
            conn.execute('''INSERT INTO player_recipe_knowledge
                (player_id, recipe_id, acquired_via, learned_location_id, gold_paid, catalog_version)
                VALUES (?, ?, 'guild', ?, ?, 1)''',
                (player_id, recipe_id, player['location_id'], recipe.learning_gold))
            result = {'schema_version': 1, 'action_kind': 'learn', 'status': 'learned',
                      'player_id': player_id, 'location_id': player['location_id'], 'recipe_id': recipe_id,
                      'consumed': [], 'granted': [], 'gold_delta': -recipe.learning_gold,
                      'gold_after': player['gold'] - recipe.learning_gold, 'progression': [],
                      'source': {'catalog_version': 1}, 'details': {}}
        store_receipt(conn, player_id, request_id, 'learn', expected_hash, result)
        conn.commit()
        return result
    except ActionRejected as exc:
        status = str(exc)
        if authorized and status not in {'stale_action', 'recipe_not_found'}:
            player = conn.execute('SELECT location_id, gold FROM players WHERE telegram_id=?', (player_id,)).fetchone()
            result = store_business_rejection(
                conn, player_id=player_id, request_id=request_id, action_kind='learn',
                request_hash=expected_hash, status=status,
                location_id=player['location_id'] if player else None,
                recipe_id=recipe_id, gold_after=player['gold'] if player else 0,
                source={'catalog_version': 1},
            )
            conn.commit()
            return result
        conn.rollback()
        return {'status': status, 'action_kind': 'learn', 'recipe_id': recipe_id}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
