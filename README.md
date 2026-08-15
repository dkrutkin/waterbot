# 💧 Water Reminder Bot

A Telegram bot that helps you keep up daily water intake: goals, reminders,
logging, progress, streaks, and history — built from the functional
requirements spec.

The bot can run two ways, sharing the same handlers/database/business-logic
code:

- **Locally, via long-polling** (`main.py`) — simplest for development.
- **On Vercel, via a webhook** (`app.py`) — for a deployment that isn't
  tied to your machine being on. See "Deploying to Vercel" below.

Only one of these can be active for a given bot at a time (Telegram will
reject long-polling while a webhook is set) — `set_webhook.py` switches
between them.

## Local setup (polling)

```bash
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # then edit .env: bot token + Supabase DATABASE_URL
python main.py
```

Get a token from [@BotFather](https://t.me/BotFather) on Telegram and put it
in `.env` as `TELEGRAM_BOT_TOKEN`.

Get your database connection string from the Supabase dashboard: open your
project, click the green **Connect** button near the top, and choose
**Session pooler** or **Transaction pooler** (works over plain IPv4) rather
than "Direct connection" unless you know your network has IPv6. Put it in
`.env` as `DATABASE_URL`. The bot creates its own tables automatically the
first time it runs — no manual schema setup needed.

## Deploying to Vercel (webhook + free external cron)

Vercel Functions are request/response — there's no long-running process to
poll Telegram or tick a scheduler in the background, so this mode works
differently: Telegram pushes updates to a webhook endpoint, and an
**external** free scheduler (not Vercel's own cron) pings a reminder-check
endpoint once a minute. This matters because Vercel's free Hobby-plan cron
jobs can only run once a day with imprecise timing — nowhere near frequent
enough for FR-06 reminder frequencies like "every 60 minutes."

1. **Push this repo to GitHub** (if you haven't already) and import it as a
   new project in the [Vercel dashboard](https://vercel.com/new). Vercel
   auto-detects `app.py` as the Python entrypoint from `requirements.txt`.

2. **Generate two random secrets** (one per command, or run twice):
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

3. **Set environment variables** in the Vercel project (Settings →
   Environment Variables): `TELEGRAM_BOT_TOKEN`, `DATABASE_URL`,
   `TELEGRAM_WEBHOOK_SECRET` (first secret from step 2), `CRON_SECRET`
   (second secret). Deploy.

4. **Point Telegram's webhook at your deployment.** Locally, with your
   `.env` containing the *same* `TELEGRAM_WEBHOOK_SECRET` you set in
   Vercel:
   ```bash
   python set_webhook.py https://your-project.vercel.app
   ```
   (To switch back to local polling later: `python set_webhook.py --delete`.)

5. **Set up the external cron pinger** for reminders. Create a free account
   at [cron-job.org](https://cron-job.org) (or any similar service) and add
   a job that:
   - Hits `https://your-project.vercel.app/cron-tick` every 1 minute
   - Sends header `x-cron-secret: <your CRON_SECRET from step 2>`

6. Message your bot on Telegram to confirm it responds. Reminders will start
   firing on the schedule each user configured, checked every time the
   external cron pings `/cron-tick`.

`requirements.txt` includes both `fastapi` (used only by `app.py`) and
`APScheduler` (used only by `main.py`) so the same file works for either run
mode — harmless either way, though you can trim whichever half you don't
need if you want a smaller Vercel bundle.

## What's implemented

- **Onboarding** (`/start`): set a daily goal, choose or auto-detect a
  timezone, set active reminder hours, and choose a reminder frequency,
  then drop into the main menu. Reminder start/end prompts include buttons
  for the default 09:00-22:00 window as well as accepting custom times.
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
- **Settings** (`/settings`): goal, reminder frequency, active hours (with
  default-time buttons or custom HH:MM input),
  notifications on/off, timezone (pick from a list, type an IANA name, or
  share your location to auto-detect via `timezonefinder`), and units
  (ml/liters).
- **Pause/resume** (`/pause`, `/resume`): stops/starts reminders only —
  consumption, goal, streak, and history are untouched.
- **Persistence**: Postgres (Supabase) via `asyncpg`, so state survives
  restarts and lives in the cloud rather than a local file. Water is logged
  as individual timestamped events; goal achievement is evaluated against
  the goal that was active on that day, per BR-07.

## Project layout

```
main.py             local entry point: aiogram polling + in-process APScheduler
app.py               Vercel entry point: FastAPI app, /webhook + /cron-tick
set_webhook.py        one-off helper to point/unpoint Telegram's webhook
config.py            static configuration/constants
database.py          Postgres/Supabase schema + queries (asyncpg)
pg_storage.py         Postgres-backed aiogram FSM storage (used by both run modes)
reminder_logic.py     the actual "who's due a reminder right now" logic
scheduler.py          wraps reminder_logic in APScheduler, for main.py only
utils.py             timezone/date helpers, streak rollover, formatting
logic.py             shared "log water + fire notifications" business logic
keyboards.py         inline keyboard builders
states.py            aiogram FSM states for multi-step conversations
handlers/             one router module per feature area
  start.py           /start + onboarding
  water.py           /water + drink logging
  progress.py         /progress
  streaks.py          /streak
  stats.py             /stats
  settings.py          /settings
  pause.py             /pause, /resume
  help.py              /help
```

## Notes / next steps if you productionize this

- FSM (conversation) state lives in Postgres (`pg_storage.py`), not memory —
  needed because Vercel Functions don't share memory between invocations,
  and it has the side benefit of surviving a local restart too.
- `timezonefinder` is optional — the bot degrades gracefully (manual
  timezone selection still works) if it isn't installed.
- For heavier load, consider moving the per-tick "loop over all users" in
  `reminder_logic.py` to a per-user job so it scales better with large user
  counts, and watch Vercel's function execution-time limit if the user
  count grows large enough that one `/cron-tick` run takes a while.
- `database.py` disables asyncpg's prepared-statement cache
  (`statement_cache_size=0`) so it works against Supabase's pgbouncer
  connection poolers, not just a direct connection.
- `users.user_id` is `BIGINT`, which comfortably covers Telegram's user ID
  range.
