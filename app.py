"""Vercel entrypoint: Telegram webhook + externally-triggered reminder tick.

This is one of two ways to run the bot — see main.py for local long-polling.
Both share the same handlers/database/logic modules.

Routes:
  POST /webhook     Telegram calls this with every update (see set_webhook.py
                     for the one-time setup call that points Telegram here).
  POST/GET /cron-tick   Call this from an external scheduler (e.g.
                     cron-job.org) roughly once a minute to send due
                     reminders — Vercel's own free-tier cron can only run
                     once/day, which isn't frequent enough for FR-05/FR-06.
  GET  /            Trivial health check.

Vercel keeps a serverless function instance "warm" across nearby requests
and reuses the same running process, so the asyncpg pool and aiogram
Bot/Dispatcher are created lazily on first use and cached at module scope
for that instance rather than rebuilt on every request.
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Update
from fastapi import FastAPI, Header, Request, Response

import config
import database as db
from handlers import all_routers
from pg_storage import PostgresStorage
from reminder_logic import run_reminder_tick

logging.basicConfig(level=logging.INFO, format=config.logging_format)
logger = logging.getLogger("waterbot.app")

app = FastAPI()

_bot: Bot | None = None
_dp: Dispatcher | None = None
_ready = False
_init_lock = asyncio.Lock()


async def _ensure_ready():
    """Lazily initialize the DB pool + bot/dispatcher exactly once per warm instance."""
    global _bot, _dp, _ready
    if _ready:
        return
    async with _init_lock:
        if _ready:  # re-check after acquiring the lock (another request may have won the race)
            return
        if not config.TOKEN:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
        if not config.DATABASE_URL:
            raise RuntimeError("DATABASE_URL is not set")

        await db.init_db()

        _bot = Bot(token=config.TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
        _dp = Dispatcher(storage=PostgresStorage())
        for router in all_routers:
            _dp.include_router(router)

        _ready = True
        logger.info("Water Reminder Bot ready (webhook mode)")


@app.get("/")
async def health():
    return {"status": "ok", "service": "water-reminder-bot"}


@app.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    if config.TELEGRAM_WEBHOOK_SECRET:
        if x_telegram_bot_api_secret_token != config.TELEGRAM_WEBHOOK_SECRET:
            return Response(status_code=401, content="unauthorized")

    await _ensure_ready()

    payload = await request.json()
    update = Update.model_validate(payload)
    await _dp.feed_webhook_update(_bot, update)
    return {"ok": True}


@app.api_route("/cron-tick", methods=["GET", "POST"])
async def cron_tick(request: Request):
    if config.CRON_SECRET:
        provided = request.headers.get("x-cron-secret") or request.query_params.get("secret")
        if provided != config.CRON_SECRET:
            return Response(status_code=401, content="unauthorized")

    await _ensure_ready()

    sent = await run_reminder_tick(_bot)
    return {"ok": True, "reminders_sent": sent}
