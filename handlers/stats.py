"""FR-14: historical daily statistics."""
import datetime as dt

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

import database as db
import keyboards as kb
import utils

router = Router(name="stats")

DAY_ABBR = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


async def _stats_text(user_id: int) -> str:
    user_row = await db.get_user(user_id)
    user_row = await utils.finalize_day_if_needed(user_row)
    units = user_row["units"]

    rows = await db.recent_daily_results(user_id, days=7)
    lines = ["📊 *Last 7 days*", ""]
    if not rows:
        lines.append("No history yet — log some water to get started!")
    else:
        for r in rows:
            date = dt.date.fromisoformat(r["date"])
            label = DAY_ABBR[date.weekday()]
            mark = " ✓" if r["achieved"] else ""
            lines.append(
                f"{label} — {utils.format_amount(r['total_ml'], units)} / {utils.format_amount(r['goal_ml'], units)}{mark}"
            )

    lines.append("")
    lines.append(f"🔥 Current streak: *{user_row['current_streak']} days*")
    lines.append(f"🏆 Longest streak: *{user_row['longest_streak']} days*")
    return "\n".join(lines)


@router.message(F.text == "/stats")
async def cmd_stats(message: Message):
    await db.create_user_if_missing(message.from_user.id)
    text = await _stats_text(message.from_user.id)
    await message.answer(text, parse_mode="Markdown", reply_markup=kb.main_menu())
