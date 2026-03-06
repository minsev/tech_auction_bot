from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import get_resale_lot_by_id, add_review, get_user_info

router = Router()

class ReviewState(StatesGroup):
    rating = State()
    comment = State()

@router.callback_query(F.data.startswith("review_"))
async def start_review(callback: CallbackQuery, state: FSMContext):
    lot_id = int(callback.data.split("_")[1])
    lot = get_resale_lot_by_id(lot_id)
    if not lot or lot[10] != 'sold':
        await callback.answer("Этот товар ещё не продан или отзыв уже оставлен.", show_alert=True)
        return
    if lot[12] != callback.from_user.id:
        await callback.answer("Вы не являетесь покупателем этого товара.", show_alert=True)
        return
    await state.update_data(lot_id=lot_id, seller_id=lot[1])
    kb = InlineKeyboardBuilder()
    for i in range(1, 6):
        kb.button(text=f"{'⭐'*i}", callback_data=f"rate_{i}")
    kb.adjust(5)
    await callback.message.answer("Оцените продавца (от 1 до 5 звёзд):", reply_markup=kb.as_markup())
    await state.set_state(ReviewState.rating)
    await callback.answer()

@router.callback_query(ReviewState.rating, F.data.startswith("rate_"))
async def process_rating(callback: CallbackQuery, state: FSMContext):
    rating = int(callback.data.split("_")[1])
    await state.update_data(rating=rating)
    await callback.message.answer("Напишите ваш отзыв текстом (можно оставить пустым, отправив '-'):")
    await state.set_state(ReviewState.comment)
    await callback.answer()

@router.message(ReviewState.comment)
async def process_comment(message: Message, state: FSMContext):
    comment = message.text.strip()
    if comment == '-':
        comment = ""
    data = await state.get_data()
    lot_id = data['lot_id']
    seller_id = data['seller_id']
    rating = data['rating']
    buyer_id = message.from_user.id
    
    if add_review(seller_id, buyer_id, lot_id, rating, comment):
        await message.answer("✅ Спасибо! Ваш отзыв сохранён.")
    else:
        await message.answer("❌ Не удалось сохранить отзыв (возможно, вы уже оставляли отзыв на этот товар).")
    await state.clear()