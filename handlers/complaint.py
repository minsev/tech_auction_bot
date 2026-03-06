from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import add_complaint, get_resale_lot_by_id, user_exists, get_user_contact
from config import ADMIN_GROUP_ID

router = Router()

class ComplaintState(StatesGroup):
    reason = State()

@router.callback_query(F.data.startswith("complaint_"))
async def start_complaint(callback: CallbackQuery, state: FSMContext):
    lot_id = int(callback.data.split("_")[1])
    if not user_exists(callback.from_user.id):
        await callback.answer("Сначала зарегистрируйтесь.", show_alert=True)
        return
    lot = get_resale_lot_by_id(lot_id)
    if not lot:
        await callback.answer("Объявление не найдено.", show_alert=True)
        return
    await state.update_data(lot_id=lot_id)
    await callback.message.answer("Опишите причину жалобы:")
    await state.set_state(ComplaintState.reason)
    await callback.answer()

@router.message(ComplaintState.reason)
async def process_complaint(message: Message, state: FSMContext):
    reason = message.text.strip()
    if not reason:
        await message.answer("Причина не может быть пустой.")
        return
    data = await state.get_data()
    lot_id = data['lot_id']
    complaint_id = add_complaint(message.from_user.id, lot_id, reason)
    await message.answer("✅ Жалоба отправлена администраторам.")
    # Уведомляем админов
    contact = get_user_contact(message.from_user.id)
    await message.bot.send_message(
        ADMIN_GROUP_ID,
        f"⚠️ Новая жалоба #{complaint_id}\n"
        f"На объявление #{lot_id}\n"
        f"От: {contact}\n"
        f"Причина: {reason}"
    )
    await state.clear()