from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import (
    user_exists, get_active_resale_lots, get_resale_lot_by_id,
    reserve_lot, get_user_contact, get_user_info
)
from keyboards import resale_lot_inline_keyboard
from config import ADMIN_GROUP_ID

router = Router()

@router.message(F.text == "🛍 Купить технику")
async def show_resale_lots(message: Message):
    if not user_exists(message.from_user.id):
        await message.answer("Сначала зарегистрируйтесь (нажмите /start).")
        return
    lots = get_active_resale_lots()
    if not lots:
        await message.answer("Нет товаров в продаже.")
        return
    for lot in lots:
        lot_id, reseller_id, category_id, brand_id, model_id, specs, description, condition, photo_id, price, created_at, status = lot
        
        if status == 'reserved':
            caption = (
                f"🔹 Объявление #{lot_id} (ЗАБРОНИРОВАНО)\n"
                f"Описание: {description}\n"
                f"Состояние: {condition}\n"
                f"Цена: {price} ₽\n"
                f"Создано: {created_at}\n"
            )
            await message.answer_photo(photo=photo_id, caption=caption)
        else:
            caption = (
                f"🔹 Объявление #{lot_id}\n"
                f"Описание: {description}\n"
                f"Состояние: {condition}\n"
                f"Цена: {price} ₽\n"
                f"Создано: {created_at}\n"
            )
            await message.answer_photo(
                photo=photo_id,
                caption=caption,
                parse_mode="HTML",
                reply_markup=resale_lot_inline_keyboard(lot_id, price)
            )

@router.callback_query(F.data.startswith("buy_"))
async def process_buy(callback: CallbackQuery):
    user_id = callback.from_user.id
    lot_id = int(callback.data.split("_")[1])
    lot = get_resale_lot_by_id(lot_id)
    if not lot or lot[10] != 'active':
        await callback.answer("Товар уже недоступен для покупки.", show_alert=True)
        return
    
    if reserve_lot(lot_id, user_id):
        reseller_id = lot[1]
        reseller_contact = get_user_contact(reseller_id)
        buyer_contact = get_user_contact(user_id)
        
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Подтвердить сделку", callback_data=f"confirm_sale_{lot_id}")
        kb.button(text="❌ Отменить резерв", callback_data=f"cancel_reserve_{lot_id}")
        kb.adjust(2)
        
        await callback.bot.send_message(
            reseller_id,
            f"🛒 Ваш товар #{lot_id} зарезервирован покупателем!\n"
            f"Свяжитесь с ним: {buyer_contact}\n"
            f"После получения денег нажмите «Подтвердить». Если сделка не состоялась – «Отменить резерв».",
            reply_markup=kb.as_markup()
        )
        
        await callback.message.answer(
            f"✅ Вы зарезервировали товар #{lot_id}!\n"
            f"Продавец: {reseller_contact}\n"
            f"Ожидайте, пока продавец подтвердит сделку после получения оплаты."
        )
        
        await callback.bot.send_message(
            ADMIN_GROUP_ID,
            f"🔔 Товар #{lot_id} зарезервирован!\n"
            f"Покупатель: {buyer_contact}\n"
            f"Продавец: {reseller_contact}\n"
            f"Цена: {lot[9]} ₽"
        )
        
        await callback.message.edit_caption(
            caption=callback.message.caption + "\n\n⏳ ЗАБРОНИРОВАНО",
            reply_markup=None
        )
    else:
        await callback.answer("Не удалось зарезервировать товар.", show_alert=True)
    await callback.answer()