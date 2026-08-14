"""Timezone, date, streak, and formatting helpers."""
import datetime as dt
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import config
import database as db


def get_tz(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def now_local(tz_name: str) -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).astimezone(get_tz(tz_name))


def today_str(tz_name: str) -> str:
    return now_local(tz_name).date().isoformat()


def is_valid_timezone(tz_name: str) -> bool:
    try:
        ZoneInfo(tz_name)
        return True
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        return False


def parse_hhmm(text: str):
    """Parse an HH:MM 24h string. Returns datetime.time or None if invalid."""
    text = text.strip()
    try:
        h, m = text.split(":")
        h, m = int(h), int(m)
        if 0 <= h <= 23 and 0 <= m <= 59:
            return dt.time(hour=h, minute=m)
    except (ValueError, AttributeError):
        pass
    return None


def in_active_window(local_time: dt.time, start: dt.time, end: dt.time) -> bool:
    """True if local_time falls within [start, end], handling overnight windows."""
    if start <= end:
        return start <= local_time <= end
    # overnight window, e.g. 22:00 -> 06:00
    return local_time >= start or local_time <= end


def progress_bar(percentage: float, length: int = 20, filled_char: str = "█", empty_char: str = "░") -> str:
    pct = max(0, min(100, percentage))
    filled = round(pct / 100 * length)
    return filled_char * filled + empty_char * (length - filled)


def format_amount(amount_ml: int, units: str) -> str:
    if units == "l":
        return f"{amount_ml / 1000:.2f} L"
    return f"{amount_ml:,} ml"


def format_progress_message(total: int, goal: int, units: str, streak: int = None) -> str:
    pct = (total / goal * 100) if goal else 0
    remaining = max(0, goal - total)
    lines = [
        "💧 *Today's Water*",
        "",
        f"*{format_amount(total, units)} / {format_amount(goal, units)}*",
        "",
        f"{progress_bar(pct)} {pct:.0f}%",
        "",
        f"Remaining: *{format_amount(remaining, units)}*",
    ]
    if streak is not None:
        lines.append("")
        lines.append(f"🔥 Streak: *{streak} day{'s' if streak != 1 else ''}*")
    return "\n".join(lines)


async def finalize_day_if_needed(user_row):
    """Roll over daily results / streaks whenever the user's local calendar
    date has advanced past what was last processed for them (FR-13).

    Returns the (possibly refreshed) user row.
    """
    user_id = user_row["user_id"]
    tz_name = user_row["timezone"]
    today = today_str(tz_name)
    last_processed = user_row["last_processed_date"]

    if last_processed is None:
        # First time we see this user process a day; nothing to finalize yet.
        await db.update_user(user_id, last_processed_date=today)
        return await db.get_user(user_id)

    if last_processed == today:
        return user_row

    last_date = dt.date.fromisoformat(last_processed)
    today_date = dt.date.fromisoformat(today)
    current_streak = user_row["current_streak"]
    longest_streak = user_row["longest_streak"]

    d = last_date
    while d < today_date:
        date_str = d.isoformat()
        total = await db.total_for_date(user_id, date_str)
        goal = user_row["daily_goal"]
        achieved = total >= goal and goal > 0
        await db.upsert_daily_result(user_id, date_str, total, goal, achieved)

        if achieved:
            current_streak += 1
        else:
            current_streak = 0
        longest_streak = max(longest_streak, current_streak)

        d += dt.timedelta(days=1)

    await db.update_user(
        user_id,
        last_processed_date=today,
        current_streak=current_streak,
        longest_streak=longest_streak,
        goal_achieved_notified_date=None,
    )
    return await db.get_user(user_id)


def is_milestone(streak: int) -> bool:
    return streak in config.STREAK_MILESTONES
