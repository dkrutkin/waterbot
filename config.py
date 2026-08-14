"""Static configuration and constants for the Water Reminder Bot."""
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Postgres connection string for Supabase, e.g.:
#   postgresql://postgres.xxxxxxxx:YOUR-PASSWORD@aws-0-region.pooler.supabase.com:5432/postgres
DATABASE_URL = os.getenv("DATABASE_URL")

# --- Defaults for a new user ---
DEFAULT_GOAL_ML = 2000
DEFAULT_REMINDER_FREQUENCY_MIN = 60
DEFAULT_REMINDER_START = "09:00"
DEFAULT_REMINDER_END = "22:00"
DEFAULT_TIMEZONE = "UTC"
DEFAULT_UNITS = "ml"

# --- Quick-log amounts (FR-03) ---
QUICK_AMOUNTS_ML = [100, 200, 250, 300, 500]

# --- Custom amount validation (FR-04) ---
MIN_AMOUNT_ML = 1
MAX_AMOUNT_ML = 3000  # reasonable ceiling for a single log entry

# --- Reminder frequency choices (FR-06) ---
FREQUENCY_CHOICES_MIN = [30, 60, 90, 120, 180]

# --- Streak milestones (FR-11) ---
STREAK_MILESTONES = [3, 7, 14, 30, 60, 100]

# --- Common timezones offered in Settings (FR-15) ---
COMMON_TIMEZONES = [
    "UTC",
    "Europe/London",
    "Europe/Berlin",
    "Europe/Moscow",
    "Asia/Tbilisi",
    "Asia/Dubai",
    "Asia/Kolkata",
    "Asia/Shanghai",
    "Asia/Tokyo",
    "Australia/Sydney",
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
]

# How often the background scheduler wakes up to check reminders / day rollovers.
SCHEDULER_TICK_SECONDS = 60

# Minimum minutes that must pass since the last log before a reminder is sent right after it
# (soft "postpone if you just logged" behavior from FR-07).
POST_LOG_REMINDER_SUPPRESS_MIN = 10

logging_format = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
