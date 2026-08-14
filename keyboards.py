"""Inline keyboard builders."""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config


def main_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="💧 Drink water", callback_data="menu:drink")
    kb.button(text="📊 Today's progress", callback_data="menu:progress")
    kb.button(text="🔥 My streak", callback_data="menu:streak")
    kb.button(text="⚙️ Settings", callback_data="menu:settings")
    kb.adjust(1)
    return kb.as_markup()


def quick_amounts(prefix: str = "drink") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for amount in config.QUICK_AMOUNTS_ML:
        kb.button(text=f"+{amount} ml", callback_data=f"{prefix}:{amount}")
    kb.button(text="✏️ Custom amount", callback_data=f"{prefix}:custom")
    kb.button(text="⬅️ Back", callback_data="menu:home")
    kb.adjust(2, 2, 1, 1, 1)
    return kb.as_markup()


def reminder_quick_log(amount: int = 250) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=f"💧 Drink {amount} ml", callback_data=f"drink:{amount}")
    kb.button(text="✏️ Custom amount", callback_data="drink:custom")
    kb.adjust(1)
    return kb.as_markup()


def settings_menu(user_row) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=f"🎯 Daily goal ({user_row['daily_goal']} ml)", callback_data="settings:goal")
    kb.button(text=f"⏱ Frequency ({user_row['reminder_frequency_min']} min)", callback_data="settings:frequency")
    kb.button(
        text=f"🕒 Active hours ({user_row['reminder_start']}-{user_row['reminder_end']})",
        callback_data="settings:hours",
    )
    paused = bool(user_row["reminders_paused"])
    notif_label = "🔕 Notifications: Paused" if paused else "🔔 Notifications: On"
    kb.button(text=notif_label, callback_data="settings:toggle_pause")
    kb.button(text=f"🌍 Timezone ({user_row['timezone']})", callback_data="settings:timezone")
    kb.button(text=f"📏 Units ({user_row['units']})", callback_data="settings:units")
    kb.button(text="⬅️ Back", callback_data="menu:home")
    kb.adjust(1)
    return kb.as_markup()


def frequency_options() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for minutes in config.FREQUENCY_CHOICES_MIN:
        label = f"{minutes} min" if minutes < 60 else f"{minutes // 60}h" + (f"{minutes % 60}m" if minutes % 60 else "")
        kb.button(text=label, callback_data=f"freq:{minutes}")
    kb.button(text="⬅️ Back", callback_data="menu:settings")
    kb.adjust(3, 2, 1)
    return kb.as_markup()


def timezone_options() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for tz in config.COMMON_TIMEZONES:
        kb.button(text=tz, callback_data=f"tz:{tz}")
    kb.button(text="📍 Share location to auto-detect", callback_data="tz:location")
    kb.button(text="✏️ Enter manually", callback_data="tz:custom")
    kb.button(text="⬅️ Back", callback_data="menu:settings")
    kb.adjust(2)
    return kb.as_markup()


def units_options() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="ml", callback_data="units:ml")
    kb.button(text="liters", callback_data="units:l")
    kb.button(text="⬅️ Back", callback_data="menu:settings")
    kb.adjust(2, 1)
    return kb.as_markup()


def back_to_settings() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Back", callback_data="menu:settings")
    return kb.as_markup()


def onboarding_goal_options() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for amount in (1500, 2000, 2500, 3000):
        kb.button(text=f"{amount} ml", callback_data=f"onboard_goal:{amount}")
    kb.button(text="✏️ Custom", callback_data="onboard_goal:custom")
    kb.adjust(2, 2, 1)
    return kb.as_markup()


def onboarding_frequency_options() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for minutes in config.FREQUENCY_CHOICES_MIN:
        label = f"{minutes} min" if minutes < 60 else f"{minutes // 60}h" + (f"{minutes % 60}m" if minutes % 60 else "")
        kb.button(text=label, callback_data=f"onboard_freq:{minutes}")
    kb.adjust(3, 2)
    return kb.as_markup()
