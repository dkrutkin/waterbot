"""FR-05/FR-06/FR-07: reminder-sending logic, shared by both run modes.

Local polling (main.py) drives this with an in-process APScheduler loop
(scheduler.py). On Vercel, an external cron pinger calls the /cron-tick
endpoint (app.py), which invokes run_reminder_tick() once per request. This
module has no dependency on APScheduler so it stays lightweight in either
deployment.

For every onboarded user, a tick:
  1. Rolls over their day if their local calendar date has advanced (FR-13).
  2. Decides whether it's time to send them a reminder, respecting their
     active hours, frequency, pause state, and whether they've already hit
     today's goal (FR-07 / BR-08).
"""
import datetime as dt
import logging

from aiogram import Bot

import config
import database as db
import keyboards as kb
import utils

logger = logging.getLogger("waterbot.reminders")


def _should_send_reminder(user_row, now_local: dt.datetime, today_total: int) -> bool:
    if not user_row["reminders_enabled"] or user_row["reminders_paused"]:
        return False
    if today_total >= user_row["daily_goal"] and user_row["daily_goal"] > 0:
        return False  # goal already reached today (FR-07)

    start_t = utils.parse_hhmm(user_row["reminder_start"]) or dt.time(9, 0)
    end_t = utils.parse_hhmm(user_row["reminder_end"]) or dt.time(22, 0)
    if not utils.in_active_window(now_local.time(), start_t, end_t):
        return False

    freq_min = user_row["reminder_frequency_min"] or config.DEFAULT_REMINDER_FREQUENCY_MIN

    # Avoid multiple reminders within the same scheduled interval.
    if user_row["last_reminder_sent_at"]:
        last_sent = dt.datetime.fromisoformat(user_row["last_reminder_sent_at"])
        if (now_local.astimezone(dt.timezone.utc) - last_sent.astimezone(dt.timezone.utc)) < dt.timedelta(minutes=freq_min):
            return False

    # Soft postpone: if the user just logged water, don't immediately nag them.
    if user_row["last_log_at"]:
        last_log = dt.datetime.fromisoformat(user_row["last_log_at"])
        if (now_local.astimezone(dt.timezone.utc) - last_log.astimezone(dt.timezone.utc)) < dt.timedelta(minutes=config.POST_LOG_REMINDER_SUPPRESS_MIN):
            return False

    return True


async def run_reminder_tick(bot: Bot) -> int:
    """Process one reminder tick for all users. Returns how many reminders were sent."""
    try:
        users = await db.all_users()
    except Exception:
        logger.exception("Failed to load users for reminder tick")
        return 0

    sent = 0
    for user_row in users:
        try:
            user_row = await utils.finalize_day_if_needed(user_row)
            tz_name = user_row["timezone"]
            now_local = utils.now_local(tz_name)
            today = now_local.date().isoformat()
            total = await db.total_for_date(user_row["user_id"], today)

            if not _should_send_reminder(user_row, now_local, total):
                continue

            remaining = max(0, user_row["daily_goal"] - total)
            suggested = min(250, remaining) if remaining else 250
            text = (
                "💧 Time to drink some water.\n\n"
                f"You've had *{utils.format_amount(total, user_row['units'])} / "
                f"{utils.format_amount(user_row['daily_goal'], user_row['units'])}* today."
            )
            await bot.send_message(
                user_row["user_id"],
                text,
                parse_mode="Markdown",
                reply_markup=kb.reminder_quick_log(suggested),
            )
            await db.update_user(
                user_row["user_id"],
                last_reminder_sent_at=dt.datetime.now(dt.timezone.utc).isoformat(),
            )
            sent += 1
        except Exception:
            logger.exception("Failed to process reminder tick for user %s", user_row["user_id"])

    return sent
