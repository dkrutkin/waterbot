"""FR help command."""
from aiogram import Router, F
from aiogram.types import Message

import keyboards as kb

router = Router(name="help")

HELP_TEXT = (
    "💧 *Water Reminder Bot — Help*\n\n"
    "/start — Start/restart onboarding\n"
    "/water [amount] — Log water (e.g. `/water 250`)\n"
    "/progress — Show today's progress\n"
    "/stats — Show last 7 days of statistics\n"
    "/streak — Show your current and best streak\n"
    "/settings — Change goal, reminders, timezone, units\n"
    "/pause — Pause reminders\n"
    "/resume — Resume reminders\n"
    "/help — Show this message"
)


@router.message(F.text == "/help")
async def cmd_help(message: Message):
    await message.answer(HELP_TEXT, parse_mode="Markdown", reply_markup=kb.main_menu())
