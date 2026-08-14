"""Persistence layer for the Water Reminder Bot.

Uses asyncpg against a Postgres database (Supabase) so all DB calls stay
non-blocking inside the aiogram event loop.

Schema:
  users          - one row per Telegram user, current settings + streak state
  water_logs     - individual drinking events (FR-16 "Water consumption")
  daily_results  - finalized per-day totals/goal/achievement, used for /stats
                    and to compute streaks without re-deriving history from
                    water_logs + a possibly-changed goal (BR-07).

Boolean-ish columns (reminders_enabled, reminders_paused, onboarded,
achieved) are kept as SMALLINT 0/1 rather than native BOOLEAN so the rest of
the codebase (which treats them as plain ints/truthy values) didn't need to
change during the SQLite -> Postgres migration.
"""
import datetime as dt
from typing import Optional

import asyncpg

import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    timezone TEXT NOT NULL DEFAULT 'UTC',
    daily_goal INTEGER NOT NULL DEFAULT 2000,
    units TEXT NOT NULL DEFAULT 'ml',
    reminder_frequency_min INTEGER NOT NULL DEFAULT 60,
    reminder_start TEXT NOT NULL DEFAULT '09:00',
    reminder_end TEXT NOT NULL DEFAULT '22:00',
    reminders_enabled SMALLINT NOT NULL DEFAULT 1,
    reminders_paused SMALLINT NOT NULL DEFAULT 0,
    current_streak INTEGER NOT NULL DEFAULT 0,
    longest_streak INTEGER NOT NULL DEFAULT 0,
    onboarded SMALLINT NOT NULL DEFAULT 0,
    onboarding_step TEXT,
    last_processed_date TEXT,
    last_reminder_sent_at TEXT,
    last_log_at TEXT,
    goal_achieved_notified_date TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS water_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    amount INTEGER NOT NULL,
    ts_utc TEXT NOT NULL,
    local_date TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_water_logs_user_date ON water_logs(user_id, local_date);

CREATE TABLE IF NOT EXISTS daily_results (
    user_id BIGINT NOT NULL,
    date TEXT NOT NULL,
    total_ml INTEGER NOT NULL,
    goal_ml INTEGER NOT NULL,
    achieved SMALLINT NOT NULL,
    PRIMARY KEY (user_id, date)
);

-- Conversation state (FSM) storage. Needed so multi-step flows (onboarding,
-- "enter a custom amount", settings text prompts) survive between separate
-- serverless invocations when running on Vercel (see pg_storage.py). Also
-- used locally so state survives a bot restart either way.
CREATE TABLE IF NOT EXISTS fsm_storage (
    storage_key TEXT PRIMARY KEY,
    state TEXT,
    data JSONB NOT NULL DEFAULT '{}'::jsonb
);
"""

_pool: Optional[asyncpg.Pool] = None


async def init_db(dsn: str = None):
    global _pool
    _pool = await asyncpg.create_pool(
        dsn=dsn or config.DATABASE_URL,
        min_size=1,
        max_size=5,
        # Supabase's "Transaction pooler" (pgbouncer) doesn't support server-side
        # prepared statements, so disable asyncpg's statement cache to stay
        # compatible with it as well as with direct/session connections.
        statement_cache_size=0,
    )
    async with _pool.acquire() as c:
        await c.execute(_SCHEMA)
    return _pool


def pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _pool


async def close_db():
    if _pool is not None:
        await _pool.close()


# --------------------------------------------------------------------------
# Users
# --------------------------------------------------------------------------

async def get_user(user_id: int) -> Optional[asyncpg.Record]:
    async with pool().acquire() as c:
        return await c.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)


async def create_user_if_missing(user_id: int) -> asyncpg.Record:
    existing = await get_user(user_id)
    if existing:
        return existing
    now = dt.datetime.utcnow().isoformat()
    async with pool().acquire() as c:
        await c.execute(
            """INSERT INTO users (user_id, timezone, daily_goal, units,
                   reminder_frequency_min, reminder_start, reminder_end,
                   reminders_enabled, reminders_paused, current_streak,
                   longest_streak, onboarded, created_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, 1, 0, 0, 0, 0, $8)
               ON CONFLICT (user_id) DO NOTHING""",
            user_id,
            config.DEFAULT_TIMEZONE,
            config.DEFAULT_GOAL_ML,
            config.DEFAULT_UNITS,
            config.DEFAULT_REMINDER_FREQUENCY_MIN,
            config.DEFAULT_REMINDER_START,
            config.DEFAULT_REMINDER_END,
            now,
        )
    return await get_user(user_id)


async def update_user(user_id: int, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k} = ${i + 1}" for i, k in enumerate(fields))
    values = list(fields.values())
    query = f"UPDATE users SET {cols} WHERE user_id = ${len(values) + 1}"
    async with pool().acquire() as c:
        await c.execute(query, *values, user_id)


async def all_users():
    async with pool().acquire() as c:
        return await c.fetch("SELECT * FROM users WHERE onboarded = 1")


# --------------------------------------------------------------------------
# Water logs
# --------------------------------------------------------------------------

async def add_water_log(user_id: int, amount: int, ts_utc: dt.datetime, local_date: str):
    async with pool().acquire() as c:
        await c.execute(
            "INSERT INTO water_logs (user_id, amount, ts_utc, local_date) VALUES ($1, $2, $3, $4)",
            user_id, amount, ts_utc.isoformat(), local_date,
        )


async def total_for_date(user_id: int, local_date: str) -> int:
    async with pool().acquire() as c:
        total = await c.fetchval(
            "SELECT COALESCE(SUM(amount), 0) FROM water_logs WHERE user_id = $1 AND local_date = $2",
            user_id, local_date,
        )
    return total or 0


# --------------------------------------------------------------------------
# Daily results / streaks
# --------------------------------------------------------------------------

async def upsert_daily_result(user_id: int, date: str, total_ml: int, goal_ml: int, achieved: bool):
    async with pool().acquire() as c:
        await c.execute(
            """INSERT INTO daily_results (user_id, date, total_ml, goal_ml, achieved)
               VALUES ($1, $2, $3, $4, $5)
               ON CONFLICT (user_id, date) DO UPDATE SET
                   total_ml = EXCLUDED.total_ml,
                   goal_ml = EXCLUDED.goal_ml,
                   achieved = EXCLUDED.achieved""",
            user_id, date, total_ml, goal_ml, int(achieved),
        )


async def get_daily_result(user_id: int, date: str) -> Optional[asyncpg.Record]:
    async with pool().acquire() as c:
        return await c.fetchrow(
            "SELECT * FROM daily_results WHERE user_id = $1 AND date = $2", user_id, date
        )


async def recent_daily_results(user_id: int, days: int = 7):
    async with pool().acquire() as c:
        rows = await c.fetch(
            "SELECT * FROM daily_results WHERE user_id = $1 ORDER BY date DESC LIMIT $2",
            user_id, days,
        )
    return list(reversed(rows))
