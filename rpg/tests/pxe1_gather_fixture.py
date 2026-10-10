"""One real finite tick for legacy profession-domain fixtures."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch

from database import get_connection,get_player


async def one_tick(player_id,profession,roll,message_id):
    from game.gathering_runtime import _source_snapshot,gather_tick_roll,start_gathering_session,commit_gathering_tick,stop_gathering_session
    from handlers.location import handle_lower_menu_gather_text
    from handlers.activities import handle_activity_buttons,activity_card
    player=dict(get_player(player_id))
    snapshot=_source_snapshot(player['location_id'],profession)
    cumulative=0
    selected=None
    for entry in snapshot['entries']:
        cumulative+=entry['chance_bp']/10000
        if roll<cumulative:
            selected=entry['item_id'];break
    seed=next(f'{n:032x}' for n in range(100000)
        if ((result:=gather_tick_roll(f'{n:032x}',1,snapshot)) or {}).get('item_id')==selected)
    message=SimpleNamespace(text='Gather',message_id=message_id,chat_id=player_id,reply_text=AsyncMock())
    update=SimpleNamespace(message=message,effective_user=SimpleNamespace(id=player_id))
    with patch('handlers.location.looks_like_lower_gather_button',return_value=True),patch('handlers.location.resolve_lower_gather_profession_button',return_value=profession):
        handled=await handle_lower_menu_gather_text(update,SimpleNamespace())
    keyboard=message.reply_text.call_args.kwargs['reply_markup']
    starts=[b.callback_data for row in keyboard.inline_keyboard for b in row if b.callback_data.startswith('px:gatherstart:')]
    if not starts: return handled,message,None
    def seeded(*args,**kwargs): return start_gathering_session(*args,**kwargs,seed=seed)
    query=SimpleNamespace(data=starts[0],from_user=SimpleNamespace(id=player_id),message=message,
                          answer=AsyncMock(),edit_message_text=AsyncMock())
    with patch('time.time',return_value=1000),patch('game.gathering_runtime.start_gathering_session',side_effect=seeded):
        await handle_activity_buttons(SimpleNamespace(callback_query=query),SimpleNamespace(user_data={}))
    conn=get_connection()
    session=conn.execute("SELECT * FROM player_gathering_sessions WHERE player_id=? AND status='running'",(player_id,)).fetchone()
    try:
        assert session
        conn.execute('BEGIN IMMEDIATE')
        result=commit_gathering_tick(conn,session['session_id'],now_ms=session['started_ms']+8000)
        terminal=stop_gathering_session(conn,player_id,session['session_id'],now_ms=session['started_ms']+8000)
        conn.commit()
    except Exception:
        conn.rollback();raise
    finally:
        conn.close()
    text,kb=activity_card(dict(get_player(player_id)),terminal,'gather',now_ms=terminal['updated_ms'])
    # Real compact session results replace the original preview.
    message.reply_text.reset_mock()
    await message.reply_text(text,reply_markup=kb)
    message.tick_result=result
    return handled,message,result
