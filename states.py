"""Finite state machine states for multi-step conversations."""
from aiogram.fsm.state import State, StatesGroup


class Onboarding(StatesGroup):
    waiting_for_goal = State()
    waiting_for_reminder_start = State()
    waiting_for_reminder_end = State()


class DrinkFlow(StatesGroup):
    waiting_for_custom_amount = State()


class SettingsFlow(StatesGroup):
    waiting_for_goal = State()
    waiting_for_hours_start = State()
    waiting_for_hours_end = State()
    waiting_for_timezone = State()
    waiting_for_frequency_custom = State()
