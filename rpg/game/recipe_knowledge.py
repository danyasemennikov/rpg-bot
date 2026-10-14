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
        result = learn_knowledge(conn,player_id,recipe_id)
        store_receipt(conn, player_id, request_id, 'learn', expected_hash, result,catalog_version=2)
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
                source={'catalog_version': 2},catalog_version=2,
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


def knowledge_spec(knowledge_id):
    from game.profession_recipes import GATHERING_MANUALS
    recipe=get_recipe(knowledge_id)
    if recipe:
        return {'knowledge_id':knowledge_id,'profession_key':recipe.profession_key,
                'tier':recipe.tier,'learning_gold':recipe.learning_gold}
    return GATHERING_MANUALS.get(knowledge_id)


def require_knowledge(conn,player_id,profession,tier,knowledge_id=None):
    from game.profession_recipes import GATHERING_MANUALS
    if knowledge_id:
        spec=knowledge_spec(knowledge_id)
        if not spec or spec['profession_key']!=profession or spec['tier']!=tier:
            raise ActionRejected('invalid_knowledge')
        ids=[knowledge_id]
    else:
        ids=[k for k,v in GATHERING_MANUALS.items() if v['profession_key']==profession and v['tier']==tier]
    if not any(conn.execute('SELECT 1 FROM player_recipe_knowledge WHERE player_id=? AND recipe_id=?',
                            (player_id,k)).fetchone() for k in ids):
        raise ActionRejected('recipe_not_known')


def learn_knowledge(conn,player_id,knowledge_id):
    from game.profession_state import get_state
    import time
    if not conn.in_transaction:
        raise RuntimeError('learning requires writer transaction')
    player=peaceful_player(conn,player_id,service='craftsmen_guild')
    spec=knowledge_spec(knowledge_id)
    if not spec:
        raise ActionRejected('recipe_not_found')
    state=get_state(conn,player_id,spec['profession_key'],registered=True)
    if state['tier']<spec['tier']:
        raise ActionRejected('profession_level_too_low')
    known=conn.execute('SELECT 1 FROM player_recipe_knowledge WHERE player_id=? AND recipe_id=?',
                       (player_id,knowledge_id)).fetchone()
    cost=0
    via='guild'
    if not known:
        voucher=conn.execute("SELECT slot FROM profession_vouchers WHERE player_id=? AND profession_key=? AND knowledge_id IS NULL ORDER BY slot LIMIT 1",
                             (player_id,spec['profession_key'])).fetchone() if spec['tier']==1 else None
        cost=0 if voucher else spec['learning_gold']
        if player['gold']<cost:
            raise ActionRejected('insufficient_gold')
        if voucher:
            via='voucher'
            conn.execute('UPDATE profession_vouchers SET knowledge_id=?,redeemed_ms=? WHERE player_id=? AND profession_key=? AND slot=?',
                         (knowledge_id,int(time.time()*1000),player_id,spec['profession_key'],voucher['slot']))
        conn.execute('UPDATE players SET gold=gold-? WHERE telegram_id=?',(cost,player_id))
        conn.execute("INSERT INTO player_recipe_knowledge(player_id,recipe_id,acquired_via,learned_location_id,gold_paid,catalog_version) VALUES (?,?,?,?,?,3)",
                     (player_id,knowledge_id,via,player['location_id'],cost))
    return {'schema_version':1,'catalog_version':3,'action_kind':'learn','status':'already_known' if known else 'learned',
            'player_id':player_id,'location_id':player['location_id'],'recipe_id':knowledge_id,
            'consumed':[],'granted':[],'gold_delta':-cost,'gold_after':player['gold']-cost,
            'progression':[],'source':{'catalog_version':3},'details':{'acquired_via':via}}
