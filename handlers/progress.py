"""FR-08: today's progress view."""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

import database as db
import keyboards as kb
import utils

router = Router(name="progress")


async def _progress_text(user_id: int) -> str:
    user_row = await db.get_user(user_id)
    user_row = await utils.finalize_day_if_needed(user_row)
    today = utils.today_str(user_row["timezone"])
    total = await db.total_for_date(user_id, today)
    return utils.format_progress_message(total, user_row["daily_goal"], user_row["units"], user_row["current_streak"])


@router.message(F.text == "/progress")
async def cmd_progress(message: Message):
    await db.create_user_if_missing(message.from_user.id)
    text = await _progress_text(message.from_user.id)
    await message.answer(text, parse_mode="Markdown", reply_markup=kb.main_menu())


@router.callback_query(F.data == "menu:progress")
async def cb_progress(callback: CallbackQuery):
    text = await _progress_text(callback.from_user.id)
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=kb.main_menu())
    await callback.answer()
