# 💧 Water Reminder Bot

A Telegram bot that helps you keep up daily water intake: goals, reminders,
logging, progress, streaks, and history — built from the functional
requirements spec.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # then edit .env and paste your bot token
python main.py
```

Get a token from [@BotFather](https://t.me/BotFather) on Telegram and put it
in `.env` as `TELEGRAM_BOT_TOKEN`.

## What's implemented

- **Onboarding** (`/start`): set a daily goal, active reminder hours, and
  reminder frequency, then drops you into the main menu.
- **Logging water** (`/water`, 💧 button): quick-add buttons for
  100/200/250/300/500 ml plus a validated custom-amount flow (positive
  integers only, capped to avoid fat-finger entries).
- **Reminders**: a background scheduler (APScheduler) ticks every minute,
  respects each user's timezone, active hours, frequency, pause state, and
  stops reminding once the daily goal is hit. It also softly postpones a
  reminder if you just logged water. Each reminder includes a one-tap
  "drink" button.
- **Progress** (`/progress`): amount, percent, progress bar, remaining, and
  current streak.
- **Goal achievement**: fires once per day the moment you cross your goal,
  and never again that day even if you keep drinking.
- **Streaks** (`/streak`): current vs. longest streak, milestone
  celebration messages at 3/7/14/30/60/100 days, and correct reset-to-zero
  on a missed day. Streak state is finalized when a user's local calendar
  day rolls over, so it's computed against the goal that applied that day
  and untouched by later goal changes.
- **Statistics** (`/stats`): last 7 days with per-day totals, goal, and a
  ✓ for days the goal was hit.
- **Settings** (`/settings`): goal, reminder frequency, active hours,
  notifications on/off, timezone (pick from a list, type an IANA name, or
  share your location to auto-detect via `timezonefinder`), and units
  (ml/liters).
- **Pause/resume** (`/pause`, `/resume`): stops/starts reminders only —
  consumption, goal, streak, and history are untouched.
- **Persistence**: SQLite via `aiosqlite`, so state survives restarts.
  Water is logged as individual timestamped events; goal achievement is
  evaluated against the goal that was active on that day, per BR-07.

## Project layout

```
main.py            entry point: wires up aiogram, DB, and the scheduler
config.py          static configuration/constants
database.py        SQLite schema + queries (aiosqlite)
utils.py           timezone/date helpers, streak rollover, formatting
logic.py           shared "log water + fire notifications" business logic
keyboards.py       inline keyboard builders
states.py          aiogram FSM states for multi-step conversations
scheduler.py        reminder background job
handlers/           one router module per feature area
  start.py          /start + onboarding
  water.py          /water + drink logging
  progress.py        /progress
  streaks.py         /streak
  stats.py            /stats
  settings.py         /settings
  pause.py            /pause, /resume
  help.py             /help
```

## Notes / next steps if you productionize this

- The FSM storage is in-memory (`MemoryStorage`); if you scale to multiple
  processes, swap it for `RedisStorage`.
- `timezonefinder` is optional — the bot degrades gracefully (manual
  timezone selection still works) if it isn't installed.
- For heavier load, consider moving the per-tick "loop over all users" in
  `scheduler.py` to a per-user APScheduler job so it scales better with
  large user counts.
