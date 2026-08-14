"""FR-16: pause/resume reminders."""
from aiogram import Router, F
from aiogram.types import Message

import database as db

router = Router(name="pause")


@router.message(F.text == "/pause")
async def cmd_pause(message: Message):
    await db.create_user_if_missing(message.from_user.id)
    await db.update_user(message.from_user.id, reminders_paused=1)
    await message.answer("🔕 Reminders are paused. Your progress, goal, and streak are unaffected. Use /resume to turn them back on.")


@router.message(F.text == "/resume")
async def cmd_resume(message: Message):
    await db.create_user_if_missing(message.from_user.id)
    await db.update_user(message.from_user.id, reminders_paused=0)
    await message.answer("🔔 Reminders resumed!")
