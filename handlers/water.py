"""FR-03/FR-04: logging water consumption, including custom amounts."""
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

import config
import database as db
import keyboards as kb
import logic
import utils
from states import DrinkFlow

router = Router(name="water")


async def _deliver_result(target, amount: int, result):
    text = logic.drink_logged_message(amount, result)
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, parse_mode="Markdown", reply_markup=kb.main_menu())
        send = target.message.answer
    else:
        await target.answer(text, parse_mode="Markdown", reply_markup=kb.main_menu())
        send = target.answer

    if result["newly_achieved"]:
        await send(logic.achievement_message(result), parse_mode="Markdown")
        if result["milestone_hit"]:
            await send(logic.milestone_message(result["milestone_hit"]), parse_mode="Markdown")


@router.message(F.text.regexp(r"^/water(\s+\d+)?$"))
async def cmd_water(message: Message):
    parts = message.text.split()
    await db.create_user_if_missing(message.from_user.id)
    if len(parts) == 2:
        amount = int(parts[1])
        if not (config.MIN_AMOUNT_ML <= amount <= config.MAX_AMOUNT_ML):
            await message.answer(
                f"Please enter an amount between {config.MIN_AMOUNT_ML} and {config.MAX_AMOUNT_ML} ml."
            )
            return
        result = await logic.record_water(message.from_user.id, amount)
        await _deliver_result(message, amount, result)
    else:
        await message.answer("How much water did you drink?", reply_markup=kb.quick_amounts())


@router.callback_query(F.data == "menu:drink")
async def menu_drink(callback: CallbackQuery):
    await callback.message.edit_text("How much water did you drink?", reply_markup=kb.quick_amounts())
    await callback.answer()


@router.callback_query(F.data.startswith("drink:"))
async def drink_quick_amount(callback: CallbackQuery, state: FSMContext):
    value = callback.data.split(":", 1)[1]
    await db.create_user_if_missing(callback.from_user.id)

    if value == "custom":
        await callback.message.edit_text("Enter the amount of water you drank, in ml:")
        await state.set_state(DrinkFlow.waiting_for_custom_amount)
        await callback.answer()
        return

    amount = int(value)
    result = await logic.record_water(callback.from_user.id, amount)
    await _deliver_result(callback, amount, result)
    await callback.answer()


@router.message(DrinkFlow.waiting_for_custom_amount)
async def drink_custom_amount_text(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.lstrip("-").isdigit():
        await message.answer("That doesn't look like a number. Please enter the amount in ml, e.g. `350`.", parse_mode="Markdown")
        return

    amount = int(text)
    if amount <= 0:
        await message.answer("Please enter a positive amount.")
        return
    if amount > config.MAX_AMOUNT_ML:
        await message.answer(f"That's more than the maximum of {config.MAX_AMOUNT_ML} ml per entry. Please enter a smaller amount.")
        return

    await state.clear()
    result = await logic.record_water(message.from_user.id, amount)
    await _deliver_result(message, amount, result)
