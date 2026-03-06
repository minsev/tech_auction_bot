from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import user_exists, get_user_contact, add_support_ticket
from config import ADMIN_GROUP_ID

router = Router()

class SupportState(StatesGroup):
    waiting_for_message = State()

@router.message(F.text == "🆘 Техподдержка")
async def support_start(message: Message, state: FSMContext):
    if not user_exists(message.from_user.id):
        await message.answer("Сначала зарегистрируйтесь через /start.")
        return
    await message.answer("Опишите вашу проблему или вопрос. Мы постараемся ответить как можно скорее.")
    await state.set_state(SupportState.waiting_for_message)

@router.message(SupportState.waiting_for_message)
async def support_message(message: Message, state: FSMContext):
    user_id = message.from_user.id
    text = message.text.strip()
    if not text:
        await message.answer("Сообщение не может быть пустым.")
        return
    
    ticket_id = add_support_ticket(user_id, text)
    contact = get_user_contact(user_id)
    
    kb = InlineKeyboardBuilder()
    kb.button(text="✉️ Ответить", url=f"tg://user?id={user_id}")
    
    await message.bot.send_message(
        ADMIN_GROUP_ID,
        f"🆘 Новое обращение в поддержку #{ticket_id}\nОт: {contact}\n\n{text}",
        reply_markup=kb.as_markup()
    )
    
    await message.answer("✅ Ваше сообщение отправлено администраторам. Ожидайте ответа.")
    await state.clear()