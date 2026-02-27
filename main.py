"""
Entry point. Wires together storage, the Telegram Application, and the
recurring RSS-poll job, then starts long-polling.
"""
import logging

from telegram.ext import Application, CommandHandler

import bot
import config
import storage


def _setup_logging() -> None:
    logging.basicConfig(
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.INFO,
    )
    # Silence noisy third-party loggers
    for name in ("httpx", "httpcore", "apscheduler"):
        logging.getLogger(name).setLevel(logging.WARNING)


def main() -> None:
    _setup_logging()
    log = logging.getLogger(__name__)

    storage.init_db()
    log.info("Database ready at %s", config.DATABASE_PATH)

    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    # Register command handlers
    app.add_handler(CommandHandler(["start", "help"], bot.cmd_start))
    app.add_handler(CommandHandler("add",        bot.cmd_add))
    app.add_handler(CommandHandler("remove",     bot.cmd_remove))
    app.add_handler(CommandHandler("list",       bot.cmd_list))
    app.add_handler(CommandHandler("categories", bot.cmd_categories))
    app.add_handler(CommandHandler("status",     bot.cmd_status))
    app.add_handler(CommandHandler("pause",     bot.cmd_pause))
    app.add_handler(CommandHandler("resume",    bot.cmd_resume))
    app.add_handler(CommandHandler("history",   bot.cmd_history))

    # Schedule the RSS polling job
    app.job_queue.run_repeating(
        bot.poll_rss,
        interval=config.POLL_INTERVAL,
        first=5,  # Small delay so bot is fully ready before first poll
        name="rss_poll",
    )

    log.info(
        "Bot started — user_id=%d  poll_interval=%ds",
        config.ALLOWED_USER_ID,
        config.POLL_INTERVAL,
    )
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
