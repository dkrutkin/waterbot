"""Shared business logic for logging water and firing notifications.

Kept separate from the aiogram handlers so both message-command handlers,
callback-button handlers, and the reminder scheduler can reuse the exact
same behavior (FR-03, FR-09, FR-11, BR-01..BR-06).
"""
import datetime as dt

import config
import database as db
import utils


async def preview_streak_if_today_achieved(user_row) -> int:
    """What the current streak *would* become if today counts as a success,
    without mutating anything. Actual persistence happens at day rollover
    (utils.finalize_day_if_needed) per BR-03/BR-04.
    """
    tz_name = user_row["timezone"]
    yesterday = (dt.date.fromisoformat(utils.today_str(tz_name)) - dt.timedelta(days=1)).isoformat()
    yesterday_result = await db.get_daily_result(user_row["user_id"], yesterday)
    if yesterday_result and yesterday_result["achieved"]:
        return user_row["current_streak"] + 1
    return 1


async def record_water(user_id: int, amount: int):
    """Log a water amount for the user "now" and return a result dict:
    {
      user_row, total, goal, units, percentage,
      newly_achieved: bool,        # goal crossed for the first time today
      preview_streak: int | None,  # only set when newly_achieved
      milestone_hit: int | None,   # streak milestone reached, if any
    }
    """
    user_row = await db.get_user(user_id)
    user_row = await utils.finalize_day_if_needed(user_row)

    tz_name = user_row["timezone"]
    today = utils.today_str(tz_name)
    now_utc = dt.datetime.now(dt.timezone.utc)

    await db.add_water_log(user_id, amount, now_utc, today)
    await db.update_user(user_id, last_log_at=now_utc.isoformat())

    total = await db.total_for_date(user_id, today)
    goal = user_row["daily_goal"]
    units = user_row["units"]
    percentage = (total / goal * 100) if goal else 0

    newly_achieved = False
    preview_streak = None
    milestone_hit = None

    already_notified = user_row["goal_achieved_notified_date"] == today
    if goal > 0 and total >= goal and not already_notified:
        newly_achieved = True
        preview_streak = await preview_streak_if_today_achieved(user_row)
        await db.update_user(user_id, goal_achieved_notified_date=today)
        if utils.is_milestone(preview_streak):
            milestone_hit = preview_streak

    return {
        "user_row": user_row,
        "total": total,
        "goal": goal,
        "units": units,
        "percentage": percentage,
        "newly_achieved": newly_achieved,
        "preview_streak": preview_streak,
        "milestone_hit": milestone_hit,
    }


def achievement_message(result) -> str:
    units = result["units"]
    return (
        "🎉 *Daily goal achieved!*\n\n"
        f"You drank *{utils.format_amount(result['total'], units)}* today.\n"
        f"Your goal was *{utils.format_amount(result['goal'], units)}*.\n\n"
        f"🔥 Current streak: *{result['preview_streak']} day{'s' if result['preview_streak'] != 1 else ''}*"
    )


def milestone_message(streak: int) -> str:
    return (
        f"🔥 *{streak}-day streak!*\n\n"
        f"You've reached your water goal for {streak} consecutive days.\n\n"
        "Keep it going!"
    )


def drink_logged_message(amount: int, result) -> str:
    units = result["units"]
    return (
        f"💧 *+{utils.format_amount(amount, units)} recorded*\n\n"
        f"Today's progress: *{utils.format_amount(result['total'], units)} / {utils.format_amount(result['goal'], units)}*\n\n"
        f"{result['percentage']:.0f}% of your daily goal completed."
    )
