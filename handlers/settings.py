"""FR-15: settings (goal, reminder frequency/hours, notifications, timezone, units)."""
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

import config
import database as db
import keyboards as kb
import utils
from states import SettingsFlow

router = Router(name="settings")

try:
    from timezonefinder import TimezoneFinder

    _tf = TimezoneFinder()
except ImportError:  # pragma: no cover - optional dependency
    _tf = None


async def _settings_text(user_id: int) -> str:
    return "⚙️ *Settings*\n\nChoose what you'd like to change:"


@router.message(F.text == "/settings")
async def cmd_settings(message: Message):
    user = await db.create_user_if_missing(message.from_user.id)
    await message.answer(await _settings_text(message.from_user.id), parse_mode="Markdown", reply_markup=kb.settings_menu(user))


@router.callback_query(F.data == "menu:settings")
async def cb_settings(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = await db.get_user(callback.from_user.id)
    await callback.message.edit_text(await _settings_text(callback.from_user.id), parse_mode="Markdown", reply_markup=kb.settings_menu(user))
    await callback.answer()


# --- Daily goal ---

@router.callback_query(F.data == "settings:goal")
async def settings_goal(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Enter your new daily goal in ml (e.g. `2200`):", parse_mode="Markdown")
    await state.set_state(SettingsFlow.waiting_for_goal)
    await callback.answer()


@router.message(SettingsFlow.waiting_for_goal)
async def settings_goal_text(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.isdigit() or not (config.MIN_AMOUNT_ML <= int(text) <= 10000):
        await message.answer("Please send a valid goal in ml, e.g. `2000`.", parse_mode="Markdown")
        return
    await db.update_user(message.from_user.id, daily_goal=int(text))
    await state.clear()
    user = await db.get_user(message.from_user.id)
    await message.answer(f"🎯 Daily goal updated to {int(text)} ml.", reply_markup=kb.settings_menu(user))


# --- Reminder frequency ---

@router.callback_query(F.data == "settings:frequency")
async def settings_frequency(callback: CallbackQuery):
    await callback.message.edit_text("How often should I remind you?", reply_markup=kb.frequency_options())
    await callback.answer()


@router.callback_query(F.data.startswith("freq:"))
async def settings_frequency_choice(callback: CallbackQuery):
    minutes = int(callback.data.split(":", 1)[1])
    await db.update_user(callback.from_user.id, reminder_frequency_min=minutes)
    user = await db.get_user(callback.from_user.id)
    await callback.message.edit_text(f"⏱ Reminder frequency set to every {minutes} minutes.", reply_markup=kb.settings_menu(user))
    await callback.answer()


# --- Active hours ---

@router.callback_query(F.data == "settings:hours")
async def settings_hours(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Send the *start* time for reminders, in HH:MM 24h format (e.g. `09:00`):",
        parse_mode="Markdown",
        reply_markup=kb.default_time(
            config.DEFAULT_REMINDER_START,
            "settings_hours_start:default",
        ),
    )
    await state.set_state(SettingsFlow.waiting_for_hours_start)
    await callback.answer()


async def _ask_settings_hours_end(target: Message, state: FSMContext):
    await target.answer(
        "Now send the *end* time, in HH:MM 24h format (e.g. `22:00`):",
        parse_mode="Markdown",
        reply_markup=kb.default_time(
            config.DEFAULT_REMINDER_END,
            "settings_hours_end:default",
        ),
    )
    await state.set_state(SettingsFlow.waiting_for_hours_end)


@router.callback_query(
    SettingsFlow.waiting_for_hours_start,
    F.data == "settings_hours_start:default",
)
async def settings_hours_start_default(callback: CallbackQuery, state: FSMContext):
    await state.update_data(hours_start=config.DEFAULT_REMINDER_START)
    await callback.message.edit_text(
        f"🕘 Reminder start set to {config.DEFAULT_REMINDER_START}."
    )
    await _ask_settings_hours_end(callback.message, state)
    await callback.answer()


@router.message(SettingsFlow.waiting_for_hours_start)
async def settings_hours_start_text(message: Message, state: FSMContext):
    t = utils.parse_hhmm(message.text or "")
    if not t:
        await message.answer("Please send a valid time like `09:00`.", parse_mode="Markdown")
        return
    await state.update_data(hours_start=message.text.strip())
    await _ask_settings_hours_end(message, state)


@router.callback_query(
    SettingsFlow.waiting_for_hours_end,
    F.data == "settings_hours_end:default",
)
async def settings_hours_end_default(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    start = data.get("hours_start", config.DEFAULT_REMINDER_START)
    end = config.DEFAULT_REMINDER_END
    await db.update_user(
        callback.from_user.id,
        reminder_start=start,
        reminder_end=end,
    )
    await state.clear()
    user = await db.get_user(callback.from_user.id)
    await callback.message.edit_text(
        f"🕒 Active hours set to {start}-{end}.",
        reply_markup=kb.settings_menu(user),
    )
    await callback.answer()


@router.message(SettingsFlow.waiting_for_hours_end)
async def settings_hours_end_text(message: Message, state: FSMContext):
    t = utils.parse_hhmm(message.text or "")
    if not t:
        await message.answer("Please send a valid time like `22:00`.", parse_mode="Markdown")
        return
    data = await state.get_data()
    start = data.get("hours_start", config.DEFAULT_REMINDER_START)
    end = message.text.strip()
    await db.update_user(message.from_user.id, reminder_start=start, reminder_end=end)
    await state.clear()
    user = await db.get_user(message.from_user.id)
    await message.answer(f"🕒 Active hours set to {start}-{end}.", reply_markup=kb.settings_menu(user))


# --- Notifications on/off (pause/resume from Settings) ---

@router.callback_query(F.data == "settings:toggle_pause")
async def settings_toggle_pause(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    new_state = 0 if user["reminders_paused"] else 1
    await db.update_user(callback.from_user.id, reminders_paused=new_state)
    user = await db.get_user(callback.from_user.id)
    label = "🔕 Reminders paused." if new_state else "🔔 Reminders resumed."
    await callback.message.edit_text(label, reply_markup=kb.settings_menu(user))
    await callback.answer()


# --- Timezone ---

@router.callback_query(F.data == "settings:timezone")
async def settings_timezone(callback: CallbackQuery):
    await callback.message.edit_text("Choose your timezone:", reply_markup=kb.timezone_options())
    await callback.answer()


@router.callback_query(F.data.startswith("tz:"))
async def settings_timezone_choice(callback: CallbackQuery, state: FSMContext):
    value = callback.data.split(":", 1)[1]

    if value == "custom":
        await callback.message.edit_text(
            "Send your timezone as an IANA name, e.g. `Asia/Tbilisi` or `America/New_York`:",
            parse_mode="Markdown",
        )
        await state.set_state(SettingsFlow.waiting_for_timezone)
        await callback.answer()
        return

    if value == "location":
        if _tf is None:
            await callback.answer("Auto-detect isn't available right now — please pick or type a timezone.", show_alert=True)
            return
        location_kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="📍 Share my location", request_location=True)]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        await callback.message.answer("Please share your location to auto-detect your timezone:", reply_markup=location_kb)
        await callback.answer()
        return

    await db.update_user(callback.from_user.id, timezone=value)
    user = await db.get_user(callback.from_user.id)
    await callback.message.edit_text(f"🌍 Timezone set to {value}.", reply_markup=kb.settings_menu(user))
    await callback.answer()


@router.message(SettingsFlow.waiting_for_timezone)
async def settings_timezone_text(message: Message, state: FSMContext):
    tz_name = (message.text or "").strip()
    if not utils.is_valid_timezone(tz_name):
        await message.answer("That doesn't look like a valid IANA timezone name. Try something like `Europe/Berlin`.", parse_mode="Markdown")
        return
    await db.update_user(message.from_user.id, timezone=tz_name)
    await state.clear()
    user = await db.get_user(message.from_user.id)
    await message.answer(f"🌍 Timezone set to {tz_name}.", reply_markup=kb.settings_menu(user))


@router.message(F.location)
async def settings_timezone_from_location(message: Message):
    if _tf is None:
        await message.answer("Auto-detect isn't available right now.", reply_markup=ReplyKeyboardRemove())
        return
    tz_name = _tf.timezone_at(lat=message.location.latitude, lng=message.location.longitude)
    if not tz_name:
        await message.answer("Couldn't determine a timezone from that location. Please pick one manually in /settings.", reply_markup=ReplyKeyboardRemove())
        return
    await db.create_user_if_missing(message.from_user.id)
    await db.update_user(message.from_user.id, timezone=tz_name)
    user = await db.get_user(message.from_user.id)
    await message.answer(f"🌍 Timezone auto-detected: {tz_name}.", reply_markup=ReplyKeyboardRemove())
    await message.answer("Settings:", reply_markup=kb.settings_menu(user))


# --- Units ---

@router.callback_query(F.data == "settings:units")
async def settings_units(callback: CallbackQuery):
    await callback.message.edit_text("Choose your preferred units:", reply_markup=kb.units_options())
    await callback.answer()


@router.callback_query(F.data.startswith("units:"))
async def settings_units_choice(callback: CallbackQuery):
    value = callback.data.split(":", 1)[1]
    await db.update_user(callback.from_user.id, units=value)
    user = await db.get_user(callback.from_user.id)
    label = "milliliters (ml)" if value == "ml" else "liters (L)"
    await callback.message.edit_text(f"📏 Units set to {label}.", reply_markup=kb.settings_menu(user))
    await callback.answer()
