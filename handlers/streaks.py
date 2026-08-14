"""FR-10/FR-12: streak view."""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

import database as db
import keyboards as kb
import utils

router = Router(name="streaks")


async def _streak_text(user_id: int) -> str:
    user_row = await db.get_user(user_id)
    user_row = await utils.finalize_day_if_needed(user_row)
    current = user_row["current_streak"]
    longest = user_row["longest_streak"]
    return (
        "🔥 *Your Streak*\n\n"
        f"Current streak: *{current} day{'s' if current != 1 else ''}*\n"
        f"Best streak: *{longest} day{'s' if longest != 1 else ''}*"
    )


@router.message(F.text == "/streak")
async def cmd_streak(message: Message):
    await db.create_user_if_missing(message.from_user.id)
    text = await _streak_text(message.from_user.id)
    await message.answer(text, parse_mode="Markdown", reply_markup=kb.main_menu())


@router.callback_query(F.data == "menu:streak")
async def cb_streak(callback: CallbackQuery):
    text = await _streak_text(callback.from_user.id)
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=kb.main_menu())
    await callback.answer()
