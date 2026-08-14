"""Entry point for running the Water Reminder Bot locally via long-polling.

Run with:  python main.py
Requires TELEGRAM_BOT_TOKEN and DATABASE_URL set in the environment or a
.env file (see .env.example).

This is one of two ways to run the bot — see app.py for the Vercel
webhook-based deployment. Both share the same handlers/database/logic
modules; this file just wires them up differently (polling + an in-process
APScheduler instead of a webhook + external cron pinger).
"""
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import config
import database as db
from handlers import all_routers
from pg_storage import PostgresStorage
from scheduler import setup_scheduler

logging.basicConfig(level=logging.INFO, format=config.logging_format)
logger = logging.getLogger("waterbot")


async def main():
    if not config.TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set. Create a .env file from .env.example.")
        sys.exit(1)
    if not config.DATABASE_URL:
        logger.error("DATABASE_URL is not set. Add your Supabase connection string to .env.")
        sys.exit(1)

    await db.init_db()

    bot = Bot(token=config.TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
    # In case a webhook was previously set (e.g. this bot was also deployed to
    # Vercel), Telegram won't deliver updates via polling until it's cleared.
    await bot.delete_webhook(drop_pending_updates=False)

    dp = Dispatcher(storage=PostgresStorage())
    for router in all_routers:
        dp.include_router(router)

    scheduler = setup_scheduler(bot)
    scheduler.start()

    logger.info("Water Reminder Bot starting (polling mode)...")
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await db.close_db()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
