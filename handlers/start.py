"""FR-01: /start and onboarding."""
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)

import config
import database as db
import keyboards as kb
import utils
from states import Onboarding

router = Router(name="start")

try:
    from timezonefinder import TimezoneFinder

    _tf = TimezoneFinder()
except ImportError:  # pragma: no cover - optional dependency
    _tf = None

WELCOME_TEXT = (
    "👋 *Welcome to the Water Reminder Bot!* 💧\n\n"
    "I'll help you stay hydrated by tracking your daily water intake, "
    "sending you reminders, and celebrating your streaks.\n\n"
    "Let's set up your daily water goal. How many *ml* would you like to "
    f"drink per day? (default is {config.DEFAULT_GOAL_ML} ml)"
)


async def show_main_menu(target, greeting: str = "What would you like to do?"):
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(greeting, reply_markup=kb.main_menu())
    else:
        await target.answer(greeting, reply_markup=kb.main_menu())


@router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext):
    await state.clear()
    user = await db.create_user_if_missing(message.from_user.id)
    if user["onboarded"]:
        await message.answer(
            "👋 Welcome back! Your bot is already set up.",
        )
        await show_main_menu(message)
        return

    await message.answer(WELCOME_TEXT, reply_markup=kb.onboarding_goal_options(), parse_mode="Markdown")
    await state.set_state(Onboarding.waiting_for_goal)


@router.callback_query(F.data.startswith("onboard_goal:"))
async def onboarding_goal_choice(callback: CallbackQuery, state: FSMContext):
    value = callback.data.split(":", 1)[1]
    if value == "custom":
        await callback.message.edit_text("Enter your daily goal in ml (e.g. `2200`):", parse_mode="Markdown")
        await state.set_state(Onboarding.waiting_for_goal)
        await callback.answer()
        return

    goal = int(value)
    await db.update_user(callback.from_user.id, daily_goal=goal)
    await _ask_timezone(callback.message, state)
    await callback.answer()


@router.message(Onboarding.waiting_for_goal)
async def onboarding_goal_text(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.isdigit() or not (config.MIN_AMOUNT_ML <= int(text) <= 10000):
        await message.answer("Please send a valid goal in ml, e.g. `2000`.", parse_mode="Markdown")
        return
    goal = int(text)
    await db.update_user(message.from_user.id, daily_goal=goal)
    await _ask_timezone(message, state)


async def _ask_timezone(target: Message, state: FSMContext):
    await target.answer(
        "🌍 Choose your timezone so reminder hours match your local time:",
        reply_markup=kb.timezone_options("onboard_tz"),
    )
    await state.set_state(Onboarding.waiting_for_timezone)


@router.callback_query(Onboarding.waiting_for_timezone, F.data.startswith("onboard_tz:"))
async def onboarding_timezone_choice(callback: CallbackQuery, state: FSMContext):
    value = callback.data.split(":", 1)[1]

    if value == "custom":
        await callback.message.edit_text(
            "Send your timezone as an IANA name, e.g. `Asia/Tbilisi` or `America/New_York`:",
            parse_mode="Markdown",
        )
        await state.set_state(Onboarding.waiting_for_timezone_text)
        await callback.answer()
        return

    if value == "location":
        if _tf is None:
            await callback.answer(
                "Auto-detect isn't available right now — please pick or type a timezone.",
                show_alert=True,
            )
            return
        location_kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="📍 Share my location", request_location=True)]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        await callback.message.answer(
            "Please share your location to auto-detect your timezone:",
            reply_markup=location_kb,
        )
        await state.set_state(Onboarding.waiting_for_timezone_location)
        await callback.answer()
        return

    await db.update_user(callback.from_user.id, timezone=value)
    await callback.message.edit_text(f"🌍 Timezone set to {value}.")
    await _ask_reminder_hours_start(callback.message, state)
    await callback.answer()


@router.message(Onboarding.waiting_for_timezone_text)
async def onboarding_timezone_text(message: Message, state: FSMContext):
    tz_name = (message.text or "").strip()
    if not utils.is_valid_timezone(tz_name):
        await message.answer(
            "That doesn't look like a valid IANA timezone name. Try something like `Europe/Berlin`.",
            parse_mode="Markdown",
        )
        return
    await db.update_user(message.from_user.id, timezone=tz_name)
    await message.answer(f"🌍 Timezone set to {tz_name}.")
    await _ask_reminder_hours_start(message, state)


@router.message(Onboarding.waiting_for_timezone_location, F.location)
async def onboarding_timezone_from_location(message: Message, state: FSMContext):
    tz_name = _tf.timezone_at(lat=message.location.latitude, lng=message.location.longitude)
    if not tz_name:
        await message.answer(
            "Couldn't determine a timezone from that location. Please choose one from the list.",
            reply_markup=ReplyKeyboardRemove(),
        )
        await _ask_timezone(message, state)
        return
    await db.update_user(message.from_user.id, timezone=tz_name)
    await message.answer(
        f"🌍 Timezone auto-detected: {tz_name}.",
        reply_markup=ReplyKeyboardRemove(),
    )
    await _ask_reminder_hours_start(message, state)


async def _ask_reminder_hours_start(target, state: FSMContext):
    text = (
        f"🎯 Great, goal set!\n\nNow, when should reminders *start*? "
        f"Send a time in HH:MM 24h format (default {config.DEFAULT_REMINDER_START}):"
    )
    await target.answer(
        text,
        parse_mode="Markdown",
        reply_markup=kb.default_time(
            config.DEFAULT_REMINDER_START,
            "onboard_hours_start:default",
        ),
    )
    await state.set_state(Onboarding.waiting_for_reminder_start)


async def _ask_reminder_hours_end(target: Message, state: FSMContext):
    await target.answer(
        f"And when should reminders *end*? Send a time in HH:MM (default {config.DEFAULT_REMINDER_END}):",
        parse_mode="Markdown",
        reply_markup=kb.default_time(
            config.DEFAULT_REMINDER_END,
            "onboard_hours_end:default",
        ),
    )
    await state.set_state(Onboarding.waiting_for_reminder_end)


@router.callback_query(
    Onboarding.waiting_for_reminder_start,
    F.data == "onboard_hours_start:default",
)
async def onboarding_hours_start_default(callback: CallbackQuery, state: FSMContext):
    await db.update_user(
        callback.from_user.id,
        reminder_start=config.DEFAULT_REMINDER_START,
    )
    await callback.message.edit_text(
        f"🕘 Reminder start set to {config.DEFAULT_REMINDER_START}."
    )
    await _ask_reminder_hours_end(callback.message, state)
    await callback.answer()


@router.message(Onboarding.waiting_for_reminder_start)
async def onboarding_hours_start(message: Message, state: FSMContext):
    t = utils.parse_hhmm(message.text or "")
    if not t:
        await message.answer("Please send a valid time like `09:00`.", parse_mode="Markdown")
        return
    await db.update_user(message.from_user.id, reminder_start=message.text.strip())
    await _ask_reminder_hours_end(message, state)


@router.callback_query(
    Onboarding.waiting_for_reminder_end,
    F.data == "onboard_hours_end:default",
)
async def onboarding_hours_end_default(callback: CallbackQuery, state: FSMContext):
    await db.update_user(
        callback.from_user.id,
        reminder_end=config.DEFAULT_REMINDER_END,
    )
    await callback.message.edit_text(
        f"🕙 Reminder end set to {config.DEFAULT_REMINDER_END}."
    )
    await _ask_reminder_frequency(callback.message, state)
    await callback.answer()


async def _ask_reminder_frequency(target: Message, state: FSMContext):
    await target.answer(
        "⏱ How often should I remind you?",
        reply_markup=kb.onboarding_frequency_options(),
    )
    await state.set_state(None)


@router.message(Onboarding.waiting_for_reminder_end)
async def onboarding_hours_end(message: Message, state: FSMContext):
    t = utils.parse_hhmm(message.text or "")
    if not t:
        await message.answer("Please send a valid time like `22:00`.", parse_mode="Markdown")
        return
    await db.update_user(message.from_user.id, reminder_end=message.text.strip())
    await _ask_reminder_frequency(message, state)


@router.callback_query(F.data.startswith("onboard_freq:"))
async def onboarding_frequency_choice(callback: CallbackQuery, state: FSMContext):
    minutes = int(callback.data.split(":", 1)[1])
    user_id = callback.from_user.id
    today = utils.today_str((await db.get_user(user_id))["timezone"])
    await db.update_user(
        user_id,
        reminder_frequency_min=minutes,
        reminders_enabled=1,
        reminders_paused=0,
        onboarded=1,
        last_processed_date=today,
    )
    await state.clear()
    await callback.message.edit_text(
        "✅ *You're all set!*\n\nReminders are now active. Use the menu below any time.",
        parse_mode="Markdown",
    )
    await callback.message.answer("Main menu:", reply_markup=kb.main_menu())
    await callback.answer()


@router.callback_query(F.data == "menu:home")
async def back_to_home(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await show_main_menu(callback)
    await callback.answer()
