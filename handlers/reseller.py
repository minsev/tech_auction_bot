from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime

from database import (
    has_role, user_exists, add_reseller_request, get_request,
    get_active_buyout_requests, get_buyout_request_by_id,
    add_offer, get_user_info, get_categories, get_brands_by_category, get_models_by_brand,
    get_specs_by_model, create_resale_lot, get_active_resale_lots, get_resale_lot_by_id,
    confirm_sale, cancel_reserve, get_user_contact, get_seller_reviews, get_seller_rating,
    subscribe_user, unsubscribe_user, get_user_subscriptions, get_user_balance,
    encode_referrer_id, get_pending_referral_by_referred, mark_reward_given, update_balance
)
from keyboards import (
    reseller_menu, buyout_request_inline_keyboard, resale_lot_inline_keyboard,
    categories_inline_keyboard, brands_inline_keyboard, models_inline_keyboard,
    specs_multiselect_keyboard, subscriptions_multiselect_keyboard
)
from config import ADMIN_GROUP_ID
from handlers.payment import show_wallet

router = Router()

class ResaleLotCreation(StatesGroup):
    category = State()
    brand = State()
    model = State()
    specs = State()
    custom_description = State()
    custom_condition = State()
    custom_photo = State()
    custom_price = State()
    use_custom = State()

class OfferState(StatesGroup):
    price = State()

class SubscriptionState(StatesGroup):
    selecting = State()

@router.message(F.text == "🔄 Я перекуп")
async def reseller_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not user_exists(user_id):
        await message.answer("Сначала зарегистрируйтесь через /start.")
        return
    if has_role(user_id, 'reseller'):
        await message.answer("Добро пожаловать, перекуп!", reply_markup=reseller_menu())
    else:
        if get_request(user_id):
            await message.answer("Вы уже подали заявку на статус перекупа. Ожидайте решения администратора.")
            return
        info = get_user_info(user_id)
        full_name = info[0] if info[0] else "Не указано"
        phone = info[1] if info[1] else "Не указан"
        username = message.from_user.username
        add_reseller_request(user_id, username, full_name, phone)
        await message.answer("✅ Заявка на статус перекупа отправлена администратору. Ожидайте подтверждения.")
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Платно", callback_data=f"approve_reseller_paid_{user_id}")
        kb.button(text="✅ Бесплатно", callback_data=f"approve_reseller_free_{user_id}")
        kb.button(text="❌ Отклонить", callback_data=f"reject_reseller_{user_id}")
        kb.adjust(2)
        await message.bot.send_message(
            ADMIN_GROUP_ID,
            f"📋 Заявка на статус перекупа от пользователя {full_name} (ID {user_id})",
            reply_markup=kb.as_markup()
        )

@router.message(F.text == "📦 Заявки на выкуп")
async def show_buyout_requests(message: Message):
    if not has_role(message.from_user.id, 'reseller'):
        await message.answer("Доступно только перекупам.")
        return
    requests = get_active_buyout_requests()
    if not requests:
        await message.answer("Нет активных заявок.")
        return
    for req in requests:
        req_id, user_id, category_id, brand_id, model_id, specs, description, condition, photo_id, desired_price, created_at = req
        user_info = get_user_info(user_id)
        user_name = user_info[0] if user_info else "Неизвестно"
        caption = (
            f"🔹 Заявка #{req_id}\n"
            f"Описание: {description}\n"
            f"Состояние: {condition}\n"
            f"Желаемая цена: {desired_price} ₽\n"
            f"Продавец: {user_name}\n"
            f"Создано: {created_at}\n"
        )
        await message.answer_photo(
            photo=photo_id,
            caption=caption,
            parse_mode="HTML",
            reply_markup=buyout_request_inline_keyboard(req_id)
        )

@router.callback_query(F.data.startswith("offer_"))
async def make_offer(callback: CallbackQuery, state: FSMContext):
    if not has_role(callback.from_user.id, 'reseller'):
        await callback.answer("Вы не перекуп", show_alert=True)
        return
    req_id = int(callback.data.split("_")[1])
    req = get_buyout_request_by_id(req_id)
    if not req or req[10] != 'active':
        await callback.answer("Заявка уже неактивна", show_alert=True)
        return
    await state.update_data(req_id=req_id)
    await callback.message.answer("Введите вашу цену (руб):")
    await state.set_state(OfferState.price)
    await callback.answer()

@router.message(OfferState.price)
async def process_offer_price(message: Message, state: FSMContext):
    try:
        price = int(message.text.strip())
        if price <= 0:
            await message.answer("Цена должна быть положительным числом. Введите цену:")
            return
        data = await state.get_data()
        req_id = data['req_id']
        user_id = message.from_user.id
        success = add_offer(req_id, user_id, price)
        if success:
            await message.answer("✅ Ваше предложение отправлено продавцу!")
        else:
            await message.answer("❌ Вы уже предлагали цену по этой заявке.")
        await state.clear()
    except ValueError:
        await message.answer("Введите целое число.")

@router.message(F.text == "➕ Создать объявление")
async def create_resale_start(message: Message, state: FSMContext):
    if not has_role(message.from_user.id, 'reseller'):
        await message.answer("Доступно только перекупам.")
        return
    await message.answer(
        "Выберите категорию товара:",
        reply_markup=categories_inline_keyboard()
    )
    await state.set_state(ResaleLotCreation.category)

@router.callback_query(ResaleLotCreation.category, F.data.startswith("cat_"))
async def resale_category_chosen(callback: CallbackQuery, state: FSMContext):
    category_id = int(callback.data.split("_")[1])
    await state.update_data(category_id=category_id)
    brands = get_brands_by_category(category_id)
    if brands:
        await callback.message.delete()
        await callback.message.answer(
            "Выберите бренд:",
            reply_markup=brands_inline_keyboard(category_id)
        )
        await state.set_state(ResaleLotCreation.brand)
        await state.update_data(use_custom=False)
    else:
        await state.update_data(use_custom=True)
        await callback.message.delete()
        await callback.message.answer("Введите название бренда (или модель) вручную:")
        await state.set_state(ResaleLotCreation.custom_description)
    await callback.answer()

@router.callback_query(ResaleLotCreation.brand, F.data.startswith("brand_"))
async def resale_brand_chosen(callback: CallbackQuery, state: FSMContext):
    brand_id = int(callback.data.split("_")[1])
    await state.update_data(brand_id=brand_id)
    models = get_models_by_brand(brand_id)
    if models:
        await callback.message.delete()
        await callback.message.answer(
            "Выберите модель:",
            reply_markup=models_inline_keyboard(brand_id)
        )
        await state.set_state(ResaleLotCreation.model)
    else:
        await state.update_data(use_custom=True)
        await callback.message.delete()
        await callback.message.answer("Введите описание товара (обязательно):")
        await state.set_state(ResaleLotCreation.custom_description)
    await callback.answer()

@router.callback_query(ResaleLotCreation.model, F.data.startswith("model_"))
async def resale_model_chosen(callback: CallbackQuery, state: FSMContext):
    model_id = int(callback.data.split("_")[1])
    await state.update_data(model_id=model_id, selected_specs=[])
    specs = get_specs_by_model(model_id)
    if specs:
        await callback.message.delete()
        await callback.message.answer(
            "Выберите характеристики (можно несколько):",
            reply_markup=specs_multiselect_keyboard(model_id, [])
        )
        await state.set_state(ResaleLotCreation.specs)
    else:
        await state.update_data(use_custom=True)
        await callback.message.delete()
        await callback.message.answer("Введите описание товара (обязательно):")
        await state.set_state(ResaleLotCreation.custom_description)
    await callback.answer()

@router.callback_query(ResaleLotCreation.specs, F.data.startswith("spec_"))
async def resale_spec_toggle(callback: CallbackQuery, state: FSMContext):
    spec_id = int(callback.data.split("_")[1])
    data = await state.get_data()
    selected = data.get('selected_specs', [])
    if spec_id in selected:
        selected.remove(spec_id)
    else:
        selected.append(spec_id)
    await state.update_data(selected_specs=selected)
    model_id = data['model_id']
    await callback.message.edit_reply_markup(
        reply_markup=specs_multiselect_keyboard(model_id, selected)
    )
    await callback.answer()

@router.callback_query(ResaleLotCreation.specs, F.data == "specs_done")
async def resale_specs_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get('selected_specs', [])
    if not selected:
        await callback.answer("Выберите хотя бы одну характеристику", show_alert=True)
        return
    specs_str = ','.join(str(s) for s in selected)
    await state.update_data(specs=specs_str)
    await callback.message.delete()
    await callback.message.answer("Введите дополнительное описание (или отправьте '-' если не требуется):")
    await state.set_state(ResaleLotCreation.custom_description)
    await callback.answer()

@router.message(ResaleLotCreation.custom_description)
async def resale_custom_description(message: Message, state: FSMContext):
    desc = message.text.strip() if message.text else ""
    if desc == '-':
        desc = ""
    await state.update_data(description=desc)
    await message.answer("Введите состояние товара (новое, б/у, как новое, требуется ремонт) (обязательно):")
    await state.set_state(ResaleLotCreation.custom_condition)

@router.message(ResaleLotCreation.custom_condition)
async def resale_custom_condition(message: Message, state: FSMContext):
    if not message.text or not message.text.strip():
        await message.answer("Состояние не может быть пустым. Введите состояние:")
        return
    await state.update_data(condition=message.text.strip())
    await message.answer("Загрузите фото товара (обязательно):")
    await state.set_state(ResaleLotCreation.custom_photo)

@router.message(ResaleLotCreation.custom_photo, F.photo)
async def resale_custom_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo=photo_id)
    await message.answer("Введите цену продажи в рублях (только число, обязательно):")
    await state.set_state(ResaleLotCreation.custom_price)

@router.message(ResaleLotCreation.custom_photo)
async def resale_custom_photo_invalid(message: Message):
    await message.answer("Пожалуйста, загрузите фото (не текст).")

@router.message(ResaleLotCreation.custom_price)
async def resale_custom_price(message: Message, state: FSMContext):
    try:
        cleaned = message.text.strip().replace(' ', '').replace(',', '')
        price = int(cleaned)
        if price <= 0:
            await message.answer("Цена должна быть положительным числом. Введите цену:")
            return
        data = await state.get_data()
        user_id = message.from_user.id

        category_id = data.get('category_id')
        brand_id = data.get('brand_id', 0)
        model_id = data.get('model_id', 0)
        specs = data.get('specs', '')
        description = data.get('description', '')
        condition = data.get('condition', '')
        photo = data.get('photo', '')

        lot_id = create_resale_lot(
            reseller_id=user_id,
            category_id=category_id,
            brand_id=brand_id,
            model_id=model_id,
            specs=specs,
            description=description,
            condition=condition,
            photo_file_id=photo,
            price=price
        )
        
        await message.answer(
            f"✅ Объявление #{lot_id} отправлено на модерацию!\n"
            f"После проверки администратором оно появится в каталоге.",
            reply_markup=reseller_menu()
        )
        
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Одобрить", callback_data=f"approve_lot_{lot_id}")
        kb.button(text="❌ Отклонить", callback_data=f"reject_lot_{lot_id}")
        kb.adjust(2)
        
        caption = (
            f"🆕 Новое объявление на модерацию!\n"
            f"ID лота: {lot_id}\n"
            f"Описание: {description}\n"
            f"Состояние: {condition}\n"
            f"Цена: {price} ₽\n"
            f"Продавец: {get_user_contact(user_id)}"
        )
        
        await message.bot.send_photo(
            chat_id=ADMIN_GROUP_ID,
            photo=photo,
            caption=caption,
            reply_markup=kb.as_markup()
        )
        
        await state.clear()
    except ValueError:
        await message.answer("Введите целое число (например, 5000).")

@router.message(F.text == "🏷 Мои объявления")
async def my_resale_lots(message: Message):
    if not has_role(message.from_user.id, 'reseller'):
        await message.answer("Доступно только перекупам.")
        return
    lots = get_active_resale_lots()
    my_lots = [lot for lot in lots if lot[1] == message.from_user.id]
    if not my_lots:
        await message.answer("У вас нет активных объявлений.")
        return
    for lot in my_lots:
        lot_id, reseller_id, category_id, brand_id, model_id, specs, description, condition, photo_id, price, created_at, status = lot
        caption = (
            f"🔹 Объявление #{lot_id}\n"
            f"Описание: {description}\n"
            f"Состояние: {condition}\n"
            f"Цена: {price} ₽\n"
            f"Статус: {status}\n"
            f"Создано: {created_at}\n"
        )
        await message.answer_photo(photo=photo_id, caption=caption)

@router.callback_query(F.data.startswith("confirm_sale_"))
async def confirm_sale_handler(callback: CallbackQuery, **kwargs):
    lot_id = int(callback.data.split("_")[2])
    lot = get_resale_lot_by_id(lot_id)
    if not lot or lot[10] != 'reserved':
        await callback.answer("Лот не в статусе резерва.", show_alert=True)
        return
    
    if confirm_sale(lot_id):
        buyer_id = lot[12]
        if buyer_id:
            await callback.bot.send_message(
                buyer_id,
                f"✅ Продавец подтвердил сделку по товару #{lot_id}!\n"
                f"Свяжитесь с ним: {get_user_contact(callback.from_user.id)}"
            )
            kb = InlineKeyboardBuilder()
            kb.button(text="⭐ Оставить отзыв", callback_data=f"review_{lot_id}")
            await callback.bot.send_message(
                buyer_id,
                f"Пожалуйста, оцените сделку с продавцом и оставьте отзыв:",
                reply_markup=kb.as_markup()
            )
            ref = get_pending_referral_by_referred(buyer_id)
            if ref:
                referral_id, referrer_id = ref
                update_balance(referrer_id, 100)
                mark_reward_given(referral_id, 100)
                await callback.bot.send_message(
                    referrer_id,
                    f"🎉 Ваш реферал совершил первую покупку! Вам начислено 100 баллов."
                )
        
        await callback.bot.send_message(
            ADMIN_GROUP_ID,
            f"✅ Сделка по товару #{lot_id} подтверждена продавцом."
        )
        
        await callback.message.edit_text(
            callback.message.text + "\n\n✅ Сделка подтверждена. Товар продан."
        )
        await callback.answer("Сделка подтверждена!")
    else:
        await callback.answer("Ошибка подтверждения.", show_alert=True)

@router.callback_query(F.data.startswith("cancel_reserve_"))
async def cancel_reserve_handler(callback: CallbackQuery, **kwargs):
    lot_id = int(callback.data.split("_")[2])
    lot = get_resale_lot_by_id(lot_id)
    if not lot or lot[10] != 'reserved':
        await callback.answer("Лот не в статусе резерва.", show_alert=True)
        return
    
    if cancel_reserve(lot_id):
        buyer_id = lot[12]
        if buyer_id:
            await callback.bot.send_message(
                buyer_id,
                f"❌ Продавец отменил резерв по товару #{lot_id}. Товар снова доступен для покупки."
            )
        
        await callback.bot.send_message(
            ADMIN_GROUP_ID,
            f"🔄 Резерв на товар #{lot_id} отменён продавцом."
        )
        
        await callback.message.edit_text(
            callback.message.text + "\n\n❌ Резерв отменён. Товар возвращён в продажу."
        )
        await callback.answer("Резерв отменён!")
    else:
        await callback.answer("Ошибка отмены резерва.", show_alert=True)

@router.message(F.text == "📝 Мои отзывы")
async def my_reviews(message: Message):
    user_id = message.from_user.id
    if not has_role(user_id, 'reseller'):
        await message.answer("Эта функция доступна только перекупам.")
        return
    rating, count = get_seller_rating(user_id)
    reviews = get_seller_reviews(user_id)
    if not reviews:
        await message.answer("У вас пока нет отзывов.")
        return
    text = f"📊 Ваш рейтинг: {rating} ⭐ ({count} отзывов)\n\n"
    for r in reviews:
        rating, comment, created_at, username, full_name = r
        buyer_name = f"@{username}" if username else full_name
        text += f"⭐ {rating}/5 от {buyer_name}\n   «{comment}»\n   {created_at.strftime('%d.%m.%Y')}\n\n"
    await message.answer(text[:4000])

@router.message(F.text == "🔔 Мои подписки")
async def my_subscriptions(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not user_exists(user_id):
        await message.answer("Сначала зарегистрируйтесь.")
        return
    current = get_user_subscriptions(user_id)
    await state.update_data(selected=current)
    await message.answer(
        "Выберите категории для подписки:",
        reply_markup=subscriptions_multiselect_keyboard(current)
    )
    await state.set_state(SubscriptionState.selecting)

@router.callback_query(SubscriptionState.selecting, F.data.startswith("sub_toggle_"))
async def sub_toggle(callback: CallbackQuery, state: FSMContext):
    data = callback.data
    data_state = await state.get_data()
    selected = data_state.get('selected', []).copy()
    if data == "sub_toggle_all":
        if None in selected:
            selected.remove(None)
        else:
            selected = [None]
    else:
        cat_id = int(data.split("_")[2])
        if cat_id in selected:
            selected.remove(cat_id)
        else:
            selected.append(cat_id)
    await state.update_data(selected=selected)
    await callback.message.edit_reply_markup(
        reply_markup=subscriptions_multiselect_keyboard(selected)
    )
    await callback.answer()

@router.callback_query(SubscriptionState.selecting, F.data == "sub_save")
async def sub_save(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    data = await state.get_data()
    selected = data.get('selected', [])
    unsubscribe_user(user_id)
    for cat_id in selected:
        subscribe_user(user_id, cat_id)
    await callback.message.answer("✅ Подписки обновлены!")
    await callback.message.delete()
    await state.clear()

@router.message(F.text == "💸 Реферальная программа")
async def referral_program(message: Message):
    user_id = message.from_user.id
    balance = get_user_balance(user_id)
    code = encode_referrer_id(user_id)
    bot_username = (await message.bot.me()).username
    ref_link = f"https://t.me/{bot_username}?start={code}"
    text = (
        f"💸 Ваш реферальный баланс: {balance} баллов\n\n"
        f"Ваша реферальная ссылка:\n{ref_link}\n\n"
        f"Приглашайте друзей! Когда они зарегистрируются и совершат первую покупку, вы получите 100 баллов.\n"
        f"Баллы можно использовать для... (скоро появится магазин бонусов)."
    )
    await message.answer(text)

@router.message(F.text == "💰 Мой кошелек")
async def reseller_wallet(message: Message):
    await show_wallet(message)