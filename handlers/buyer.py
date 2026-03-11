# handlers/buyer.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime

from database import (
    user_exists, get_active_resale_lots, get_resale_lot_by_id,
    reserve_lot, get_user_contact, get_user_info, is_favorite, add_favorite, remove_favorite,
    get_seller_rating, increment_lot_views, add_price_offer,
    log_action, get_user_balance
)
from keyboards import resale_lot_inline_keyboard
from config import ADMIN_GROUP_ID

router = Router()

class PriceOfferState(StatesGroup):
    waiting_for_price = State()

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
        (lot_id, reseller_id, category_id, brand_id, model_id, specs, description, condition,
         photo_file_ids, video_file_id, price,
         battery_cycles, max_capacity, display_replaced, defects, accessories,
         views, offers_count, reserve_count, created_at, status) = lot
        photo_list = photo_file_ids.split(',') if photo_file_ids else []
        photo_id = photo_list[0] if photo_list else None
        seller_contact = get_user_contact(reseller_id)
        rating, count = get_seller_rating(reseller_id)
        rating_text = f"⭐ {rating} ({count} отзывов)" if rating else "⭐ нет отзывов"
        
        # Проверяем, в избранном ли этот лот у пользователя
        user_id = message.from_user.id
        fav = is_favorite(user_id, lot_id)
        
        # Исправление: преобразуем строку даты в datetime
        dt = datetime.fromisoformat(created_at.replace(' ', 'T'))
        
        caption = (
            f"🔹 Объявление #{lot_id}\n"
            f"📝 {description}\n"
            f"📦 Состояние: {condition}\n"
            f"🔋 Циклов: {battery_cycles}, Ёмкость: {max_capacity}%\n"
            f"📱 Дисплей: {display_replaced}\n"
            f"🔧 Дефекты: {defects}\n"
            f"📦 Комплект: {accessories}\n"
            f"💰 Цена: {price} ₽\n"
            f"👤 Продавец: {seller_contact} {rating_text}\n"
            f"👁 Просмотров: {views}\n"
            f"🕐 Создано: {dt.strftime('%Y-%m-%d %H:%M')}\n"
        )
        if status == 'reserved':
            caption += "⏳ ЗАБРОНИРОВАНО\n"
        if photo_id:
            await message.answer_photo(
                photo=photo_id,
                caption=caption,
                parse_mode="HTML",
                reply_markup=resale_lot_inline_keyboard(lot_id, price, is_favorite=fav)
            )
        else:
            await message.answer(caption, reply_markup=resale_lot_inline_keyboard(lot_id, price, is_favorite=fav))
        # Увеличиваем счётчик просмотров
        increment_lot_views(lot_id)

@router.callback_query(F.data.startswith("buy_"))
async def process_buy(callback: CallbackQuery):
    user_id = callback.from_user.id
    lot_id = int(callback.data.split("_")[1])
    lot = get_resale_lot_by_id(lot_id)
    if not lot or lot[19] != 'active':  # status
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
        
        # Обновляем сообщение с лотом (убираем кнопки покупки и предложения)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.edit_caption(
            caption=callback.message.caption + "\n\n⏳ ЗАБРОНИРОВАНО"
        )
        log_action(user_id, 'RESERVE_LOT', f'Лот #{lot_id}')
    else:
        await callback.answer("Не удалось зарезервировать товар.", show_alert=True)
    await callback.answer()

@router.callback_query(F.data.startswith("fav_"))
async def toggle_favorite(callback: CallbackQuery):
    user_id = callback.from_user.id
    lot_id = int(callback.data.split("_")[1])
    lot = get_resale_lot_by_id(lot_id)
    if not lot:
        await callback.answer("Лот не найден", show_alert=True)
        return
    price = lot[9]
    if is_favorite(user_id, lot_id):
        remove_favorite(user_id, lot_id)
        await callback.answer("❌ Удалено из избранного")
    else:
        add_favorite(user_id, lot_id, price)
        await callback.answer("✅ Добавлено в избранное")
    # Обновляем клавиатуру
    new_fav_status = not is_favorite(user_id, lot_id)  # после изменения
    await callback.message.edit_reply_markup(
        reply_markup=resale_lot_inline_keyboard(lot_id, price, is_favorite=new_fav_status)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("offer_price_"))
async def offer_price_start(callback: CallbackQuery, state: FSMContext):
    lot_id = int(callback.data.split("_")[2])
    lot = get_resale_lot_by_id(lot_id)
    if not lot or lot[19] != 'active':
        await callback.answer("Этот лот уже недоступен для предложений.", show_alert=True)
        return
    await state.update_data(lot_id=lot_id)
    await callback.message.answer("Введите вашу цену предложения (в рублях):")
    await state.set_state(PriceOfferState.waiting_for_price)
    await callback.answer()

@router.message(PriceOfferState.waiting_for_price)
async def process_offer_price(message: Message, state: FSMContext):
    try:
        price = int(message.text.strip())
        if price <= 0:
            await message.answer("Цена должна быть положительным числом.")
            return
        data = await state.get_data()
        lot_id = data['lot_id']
        user_id = message.from_user.id
        lot = get_resale_lot_by_id(lot_id)
        if not lot:
            await message.answer("Лот не найден.")
            await state.clear()
            return
        reseller_id = lot[1]
        offer_id = add_price_offer(lot_id, user_id, price)
        await message.answer("✅ Ваше предложение отправлено продавцу!")
        # Уведомляем продавца
        buyer_contact = get_user_contact(user_id)
        await message.bot.send_message(
            reseller_id,
            f"💰 Новое предложение цены на ваш лот #{lot_id}\n"
            f"Покупатель {buyer_contact} предлагает {price} ₽.\n"
            f"Чтобы принять или отклонить, используйте команды /accept_offer {offer_id} или /reject_offer {offer_id} в личных сообщениях с ботом."
        )
        log_action(user_id, 'PRICE_OFFER', f'Лот #{lot_id}, цена {price}')
        await state.clear()
    except ValueError:
        await message.answer("Введите целое число.")