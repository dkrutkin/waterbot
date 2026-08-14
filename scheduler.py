"""In-process reminder scheduler for local polling mode (main.py).

This wraps reminder_logic.run_reminder_tick() in an APScheduler interval job.
It is NOT used on Vercel — there, an external cron pinger hits /cron-tick on
app.py instead, since a Vercel Function can't keep a background loop alive
between requests. Keeping APScheduler isolated to this module keeps it out
of the Vercel deployment's dependency footprint entirely.
"""
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
from reminder_logic import run_reminder_tick


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_reminder_tick,
        "interval",
        seconds=config.SCHEDULER_TICK_SECONDS,
        args=[bot],
        id="water_reminder_tick",
        misfire_grace_time=30,
        coalesce=True,
        max_instances=1,
    )
    return scheduler
