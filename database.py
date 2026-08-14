"""Persistence layer for the Water Reminder Bot.

Uses aiosqlite so all DB calls stay non-blocking inside the aiogram event loop.
Schema:
  users          - one row per Telegram user, current settings + streak state
  water_logs     - individual drinking events (FR-16 "Water consumption")
  daily_results  - finalized per-day totals/goal/achievement, used for /stats
                    and to compute streaks without re-deriving history from
                    water_logs + a possibly-changed goal (BR-07).
"""
import datetime as dt
from typing import Optional

import aiosqlite

import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    timezone TEXT NOT NULL DEFAULT 'UTC',
    daily_goal INTEGER NOT NULL DEFAULT 2000,
    units TEXT NOT NULL DEFAULT 'ml',
    reminder_frequency_min INTEGER NOT NULL DEFAULT 60,
    reminder_start TEXT NOT NULL DEFAULT '09:00',
    reminder_end TEXT NOT NULL DEFAULT '22:00',
    reminders_enabled INTEGER NOT NULL DEFAULT 1,
    reminders_paused INTEGER NOT NULL DEFAULT 0,
    current_streak INTEGER NOT NULL DEFAULT 0,
    longest_streak INTEGER NOT NULL DEFAULT 0,
    onboarded INTEGER NOT NULL DEFAULT 0,
    onboarding_step TEXT,
    last_processed_date TEXT,
    last_reminder_sent_at TEXT,
    last_log_at TEXT,
    goal_achieved_notified_date TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS water_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    amount INTEGER NOT NULL,
    ts_utc TEXT NOT NULL,
    local_date TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_water_logs_user_date ON water_logs(user_id, local_date);

CREATE TABLE IF NOT EXISTS daily_results (
    user_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    total_ml INTEGER NOT NULL,
    goal_ml INTEGER NOT NULL,
    achieved INTEGER NOT NULL,
    PRIMARY KEY (user_id, date)
);
"""

_conn: Optional[aiosqlite.Connection] = None


async def init_db(path: str = None):
    global _conn
    _conn = await aiosqlite.connect(path or config.DB_PATH)
    _conn.row_factory = aiosqlite.Row
    await _conn.executescript(_SCHEMA)
    await _conn.commit()
    return _conn


def conn() -> aiosqlite.Connection:
    if _conn is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _conn


async def close_db():
    if _conn is not None:
        await _conn.close()


# --------------------------------------------------------------------------
# Users
# --------------------------------------------------------------------------

async def get_user(user_id: int) -> Optional[aiosqlite.Row]:
    cur = await conn().execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = await cur.fetchone()
    await cur.close()
    return row


async def create_user_if_missing(user_id: int) -> aiosqlite.Row:
    existing = await get_user(user_id)
    if existing:
        return existing
    now = dt.datetime.utcnow().isoformat()
    await conn().execute(
        """INSERT INTO users (user_id, timezone, daily_goal, units,
               reminder_frequency_min, reminder_start, reminder_end,
               reminders_enabled, reminders_paused, current_streak,
               longest_streak, onboarded, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, 1, 0, 0, 0, 0, ?)""",
        (
            user_id,
            config.DEFAULT_TIMEZONE,
            config.DEFAULT_GOAL_ML,
            config.DEFAULT_UNITS,
            config.DEFAULT_REMINDER_FREQUENCY_MIN,
            config.DEFAULT_REMINDER_START,
            config.DEFAULT_REMINDER_END,
            now,
        ),
    )
    await conn().commit()
    return await get_user(user_id)


async def update_user(user_id: int, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [user_id]
    await conn().execute(f"UPDATE users SET {cols} WHERE user_id = ?", values)
    await conn().commit()


async def all_users():
    cur = await conn().execute("SELECT * FROM users WHERE onboarded = 1")
    rows = await cur.fetchall()
    await cur.close()
    return rows


# --------------------------------------------------------------------------
# Water logs
# --------------------------------------------------------------------------

async def add_water_log(user_id: int, amount: int, ts_utc: dt.datetime, local_date: str):
    await conn().execute(
        "INSERT INTO water_logs (user_id, amount, ts_utc, local_date) VALUES (?, ?, ?, ?)",
        (user_id, amount, ts_utc.isoformat(), local_date),
    )
    await conn().commit()


async def total_for_date(user_id: int, local_date: str) -> int:
    cur = await conn().execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM water_logs WHERE user_id = ? AND local_date = ?",
        (user_id, local_date),
    )
    row = await cur.fetchone()
    await cur.close()
    return row["total"] if row else 0


# --------------------------------------------------------------------------
# Daily results / streaks
# --------------------------------------------------------------------------

async def upsert_daily_result(user_id: int, date: str, total_ml: int, goal_ml: int, achieved: bool):
    await conn().execute(
        """INSERT INTO daily_results (user_id, date, total_ml, goal_ml, achieved)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(user_id, date) DO UPDATE SET
               total_ml = excluded.total_ml,
               goal_ml = excluded.goal_ml,
               achieved = excluded.achieved""",
        (user_id, date, total_ml, goal_ml, int(achieved)),
    )
    await conn().commit()


async def get_daily_result(user_id: int, date: str) -> Optional[aiosqlite.Row]:
    cur = await conn().execute(
        "SELECT * FROM daily_results WHERE user_id = ? AND date = ?", (user_id, date)
    )
    row = await cur.fetchone()
    await cur.close()
    return row


async def recent_daily_results(user_id: int, days: int = 7):
    cur = await conn().execute(
        "SELECT * FROM daily_results WHERE user_id = ? ORDER BY date DESC LIMIT ?",
        (user_id, days),
    )
    rows = await cur.fetchall()
    await cur.close()
    return list(reversed(rows))
