"""Entry point for the Water Reminder Bot.

Run with:  python main.py
Requires TELEGRAM_BOT_TOKEN set in the environment or a .env file
(see .env.example).
"""
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

import config
import database as db
from handlers import all_routers
from scheduler import setup_scheduler

logging.basicConfig(level=logging.INFO, format=config.logging_format)
logger = logging.getLogger("waterbot")


async def main():
    if not config.TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set. Create a .env file from .env.example.")
        sys.exit(1)

    await db.init_db()

    bot = Bot(token=config.TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
    dp = Dispatcher(storage=MemoryStorage())
    for router in all_routers:
        dp.include_router(router)

    scheduler = setup_scheduler(bot)
    scheduler.start()

    logger.info("Water Reminder Bot starting...")
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
