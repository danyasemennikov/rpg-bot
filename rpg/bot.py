import sys
sys.path.append('/content/rpg_bot')

from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    MessageHandler, CallbackQueryHandler, filters
)

from database import init_db
from handlers.start    import start_command, handle_name_input, handle_stat_buttons
from handlers.profile  import help_command, profile_command, stats_command, handle_stats_buttons, unstuck_command, main_keyboard
from handlers.location import location_command, handle_location_buttons, handle_combat_buttons
from handlers.battle   import handle_battle_buttons
from handlers.inventory import inventory_command, handle_inventory_buttons, handle_transfer_input
from handlers.skills_ui import skills_command, handle_skills_buttons
from handlers.settings import settings_command, handle_settings_buttons

BOT_TOKEN = "8680028003:AAFzt3wkJp862HKKke_yPvoXhFWTgCbSC3I"

async def regen_tick(context):
    """Каждую минуту регенерирует всех игроков вне боя."""
    from database import get_connection
    from game.regen import apply_regen
    conn = get_connection()
    players = conn.execute(
        'SELECT * FROM players WHERE in_battle=0'
    ).fetchall()
    conn.close()
    for p in players:
        apply_regen(dict(p))

async def handle_text(update, context):
    """Роутер текстовых сообщений."""
    if await handle_transfer_input(update, context):
        return
    await handle_name_input(update, context)

def main():
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Фоновый реген каждую минуту
    job_queue = app.job_queue
    if job_queue is None:
        raise RuntimeError(
            'JobQueue недоступен. Установи: pip install "python-telegram-bot[job-queue]"'
        )
    job_queue.run_repeating(regen_tick, interval=60, first=10)

    # Команды
    app.add_handler(CommandHandler('start',    start_command))
    app.add_handler(CommandHandler('help',     help_command))
    app.add_handler(CommandHandler('profile',  profile_command))
    app.add_handler(CommandHandler('location', location_command))
    app.add_handler(CommandHandler('stats',    stats_command))
    app.add_handler(CommandHandler('unstuck',  unstuck_command))
    app.add_handler(CommandHandler('inventory', inventory_command))
    app.add_handler(CommandHandler('skills', skills_command))
    app.add_handler(CommandHandler('settings', settings_command))

    # Колбэки
    app.add_handler(CallbackQueryHandler(handle_stat_buttons,     pattern='^stat_'))
    app.add_handler(CallbackQueryHandler(handle_location_buttons, pattern='^(goto_|noop)'))
    app.add_handler(CallbackQueryHandler(handle_combat_buttons,   pattern='^(fight_|flee_)'))
    app.add_handler(CallbackQueryHandler(handle_battle_buttons,   pattern='^battle_'))
    app.add_handler(CallbackQueryHandler(handle_stats_buttons,    pattern='^sp_'))
    app.add_handler(CallbackQueryHandler(handle_inventory_buttons, pattern='^inv_'))
    app.add_handler(CallbackQueryHandler(handle_skills_buttons, pattern='^sk_'))
    app.add_handler(CallbackQueryHandler(handle_settings_buttons, pattern='^settings_'))

    # Кнопки клавиатуры — матчим по emoji (работает на всех языках)
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^📍"), location_command))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^👤"), profile_command))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^📊"), stats_command))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^❓"), help_command))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🎒"), inventory_command))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🔮"), skills_command))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^⚙️"), settings_command))
   # app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^📋"), quests_command))  # когда будет готов
   
   # Текстовый роутер — всегда последним!
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print('🚀 Осколки Вечности запущены!')
    app.run_polling()

if __name__ == '__main__':
    main()