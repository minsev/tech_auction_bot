import sqlite3
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
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
    encode_referrer_id, get_pending_referral_by_referred, mark_reward_given, update_balance,
    get_user_reliability, update_reliability, block_user, is_user_blocked, mark_offer_notified,
    add_price_offer, get_price_offers_for_lot, update_price_offer_status,
    log_action, is_favorite, add_favorite, remove_favorite,
    increment_lot_views, increment_lot_offers_count, increment_lot_reserve_count
)
from keyboards import (
    reseller_menu, buyout_request_inline_keyboard, resale_lot_inline_keyboard,
    categories_inline_keyboard, brands_inline_keyboard, models_inline_keyboard,
    specs_multiselect_keyboard, subscriptions_multiselect_keyboard, subscription_settings_keyboard
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
    photos = State()
    video = State()
    custom_price = State()
    use_custom = State()
    battery_cycles = State()
    max_capacity = State()
    display_replaced = State()
    defects = State()
    accessories = State()

class OfferState(StatesGroup):
    price = State()

class SubscriptionState(StatesGroup):
    selecting = State()
    category_settings = State()

@router.message(F.text == "🔄 Я перекуп")
async def reseller_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not user_exists(user_id):
        await message.answer("Сначала зарегистрируйтесь через /start.")
        return
    if is_user_blocked(user_id):
        await message.answer("⛔ Ваш аккаунт заблокирован. Обратитесь в поддержку.")
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
    user_id = message.from_user.id
    if not has_role(user_id, 'reseller'):
        await message.answer("Доступно только перекупам.")
        return
    if is_user_blocked(user_id):
        await message.answer("⛔ Ваш аккаунт заблокирован.")
        return
    requests = get_active_buyout_requests()
    if not requests:
        await message.answer("Нет активных заявок.")
        return
    for req in requests:
        (req_id, user_id, category_id, brand_id, model_id, specs, description, condition,
         photo_file_ids, video_file_id, desired_price,
         battery_cycles, max_capacity, display_replaced, defects, accessories,
         created_at) = req
        photo_list = photo_file_ids.split(',') if photo_file_ids else []
        photo_id = photo_list[0] if photo_list else None
        user_info = get_user_info(user_id)
        user_name = user_info[0] if user_info else "Неизвестно"
        caption = (
            f"🔹 Заявка #{req_id}\n"
            f"Описание: {description}\n"
            f"Состояние: {condition}\n"
            f"Циклов: {battery_cycles}\n"
            f"Ёмкость: {max_capacity}%\n"
            f"Дисплей: {display_replaced}\n"
            f"Дефекты: {defects}\n"
            f"Комплект: {accessories}\n"
            f"Желаемая цена: {desired_price} ₽\n"
            f"Продавец: {user_name}\n"
            f"Создано: {created_at}\n"
        )
        if photo_id:
            await message.answer_photo(
                photo=photo_id,
                caption=caption,
                parse_mode="HTML",
                reply_markup=buyout_request_inline_keyboard(req_id)
            )
        else:
            await message.answer(caption, reply_markup=buyout_request_inline_keyboard(req_id))

@router.callback_query(F.data.startswith("offer_"))
async def make_offer(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not has_role(user_id, 'reseller'):
        await callback.answer("Вы не перекуп", show_alert=True)
        return
    if is_user_blocked(user_id):
        await callback.answer("Ваш аккаунт заблокирован", show_alert=True)
        return
    req_id = int(callback.data.split("_")[1])
    req = get_buyout_request_by_id(req_id)
    if not req or req[16] != 'active':  # status
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
            # Уведомление продавца
            req = get_buyout_request_by_id(req_id)
            if req:
                seller_id = req[1]
                seller_contact = get_user_contact(seller_id)
                reseller_contact = get_user_contact(user_id)
                await message.bot.send_message(
                    seller_id,
                    f"💰 Новое предложение по вашей заявке #{req_id}!\n"
                    f"Перекуп {reseller_contact} предлагает {price} ₽.\n"
                    f"Посмотреть все предложения можно в разделе «Мои заявки»."
                )
                mark_offer_notified(req_id, user_id)
        else:
            await message.answer("❌ Вы уже предлагали цену по этой заявке.")
        await state.clear()
    except ValueError:
        await message.answer("Введите целое число.")

@router.message(F.text == "➕ Создать объявление")
async def create_resale_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not has_role(user_id, 'reseller'):
        await message.answer("Доступно только перекупам.")
        return
    if is_user_blocked(user_id):
        await message.answer("⛔ Ваш аккаунт заблокирован.")
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
    await state.update_data(specs=specs_str, description="", condition="")
    await callback.message.delete()
    await callback.message.answer("Загрузите фотографии товара (до 5 штук). После загрузки каждой фотографии выберите действие.")
    await state.update_data(photos=[])
    await state.set_state(ResaleLotCreation.photos)
    await callback.answer()

@router.message(ResaleLotCreation.custom_description)
async def resale_custom_description(message: Message, state: FSMContext):
    desc = message.text.strip()
    if not desc:
        await message.answer("Описание не может быть пустым.")
        return
    await state.update_data(description=desc, condition="")
    await message.answer("Загрузите фотографии товара (до 5 штук). После загрузки каждой фотографии выберите действие.")
    await state.update_data(photos=[])
    await state.set_state(ResaleLotCreation.photos)

@router.message(ResaleLotCreation.photos, F.photo)
async def resale_photos(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get('photos', [])
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)
    if len(photos) >= 5:
        await message.answer("Достигнут лимит фотографий (5). Переходим к загрузке видео.")
        await message.answer("Загрузите видео (необязательно) или отправьте '-' для пропуска:")
        await state.set_state(ResaleLotCreation.video)
    else:
        kb = InlineKeyboardBuilder()
        kb.button(text="📷 Загрузить ещё", callback_data="add_more_photo")
        kb.button(text="✅ Готово", callback_data="photos_done")
        await message.answer(f"Загружено {len(photos)}/5 фото. Выберите действие:", reply_markup=kb.as_markup())

@router.callback_query(ResaleLotCreation.photos, F.data == "add_more_photo")
async def resale_add_more_photo(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await callback.message.answer("Загрузите следующее фото:")
    await callback.answer()

@router.callback_query(ResaleLotCreation.photos, F.data == "photos_done")
async def resale_photos_done(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await callback.message.answer("Загрузите видео (необязательно) или отправьте '-' для пропуска:")
    await state.set_state(ResaleLotCreation.video)
    await callback.answer()

@router.message(ResaleLotCreation.video, F.video)
async def resale_video(message: Message, state: FSMContext):
    video_id = message.video.file_id
    await state.update_data(video=video_id)
    await message.answer("Введите цену продажи в рублях (только число):")
    await state.set_state(ResaleLotCreation.custom_price)

@router.message(ResaleLotCreation.video)
async def resale_video_skip(message: Message, state: FSMContext):
    if message.text == '-':
        await state.update_data(video=None)
        await message.answer("Введите цену продажи в рублях (только число):")
        await state.set_state(ResaleLotCreation.custom_price)
    else:
        await message.answer("Отправьте видео или '-' для пропуска.")

@router.message(ResaleLotCreation.custom_price)
async def resale_custom_price(message: Message, state: FSMContext):
    try:
        cleaned = message.text.strip().replace(' ', '').replace(',', '')
        price = int(cleaned)
        if price <= 0:
            await message.answer("Цена должна быть положительным числом. Введите цену:")
            return
        await state.update_data(price=price)
        await message.answer("Введите количество циклов перезарядки (если известно, иначе 0):")
        await state.set_state(ResaleLotCreation.battery_cycles)
    except ValueError:
        await message.answer("Введите целое число (например, 5000).")

@router.message(ResaleLotCreation.battery_cycles)
async def resale_battery_cycles(message: Message, state: FSMContext):
    try:
        cycles = int(message.text.strip())
        await state.update_data(battery_cycles=cycles)
        await message.answer("Введите максимальную ёмкость аккумулятора в % (например, 85):")
        await state.set_state(ResaleLotCreation.max_capacity)
    except ValueError:
        await message.answer("Введите целое число.")

@router.message(ResaleLotCreation.max_capacity)
async def resale_max_capacity(message: Message, state: FSMContext):
    try:
        capacity = int(message.text.strip())
        await state.update_data(max_capacity=capacity)
        await message.answer("Был ли переклеен дисплей? (Да/Нет):")
        await state.set_state(ResaleLotCreation.display_replaced)
    except ValueError:
        await message.answer("Введите целое число.")

@router.message(ResaleLotCreation.display_replaced)
async def resale_display_replaced(message: Message, state: FSMContext):
    text = message.text.strip().lower()
    if text in ['да', 'нет']:
        await state.update_data(display_replaced=text)
        await message.answer("Опишите дефекты (если есть, иначе '-'):")
        await state.set_state(ResaleLotCreation.defects)
    else:
        await message.answer("Введите 'Да' или 'Нет'.")

@router.message(ResaleLotCreation.defects)
async def resale_defects(message: Message, state: FSMContext):
    defects = message.text.strip()
    if defects == '-':
        defects = ''
    await state.update_data(defects=defects)
    await message.answer("Что входит в комплект? (перечислите через запятую или '-' если ничего):")
    await state.set_state(ResaleLotCreation.accessories)

@router.message(ResaleLotCreation.accessories)
async def resale_accessories(message: Message, state: FSMContext):
    accessories = message.text.strip()
    if accessories == '-':
        accessories = ''
    data = await state.get_data()
    user_id = message.from_user.id

    lot_id = create_resale_lot(
        reseller_id=user_id,
        category_id=data['category_id'],
        brand_id=data.get('brand_id', 0),
        model_id=data.get('model_id', 0),
        specs=data.get('specs', ''),
        description=data.get('description', ''),
        condition=data.get('condition', ''),
        photo_file_ids=data.get('photos', []),
        video_file_id=data.get('video'),
        price=data['price'],
        battery_cycles=data.get('battery_cycles'),
        max_capacity=data.get('max_capacity'),
        display_replaced=data.get('display_replaced'),
        defects=data.get('defects'),
        accessories=accessories
    )
    await message.answer(
        f"✅ Объявление #{lot_id} отправлено на модерацию!\n"
        f"После проверки администратором оно появится в каталоге.",
        reply_markup=reseller_menu()
    )
    # Уведомление админам
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Одобрить", callback_data=f"approve_lot_{lot_id}")
    kb.button(text="❌ Отклонить", callback_data=f"reject_lot_{lot_id}")
    kb.adjust(2)
    photo_list = data.get('photos', [])
    first_photo = photo_list[0] if photo_list else None
    if first_photo:
        await message.bot.send_photo(
            chat_id=ADMIN_GROUP_ID,
            photo=first_photo,
            caption=f"🆕 Новое объявление на модерацию #{lot_id}\nОписание: {data.get('description')}\nЦена: {data['price']} ₽\nПродавец: {get_user_contact(user_id)}",
            reply_markup=kb.as_markup()
        )
    else:
        await message.bot.send_message(
            ADMIN_GROUP_ID,
            f"🆕 Новое объявление на модерацию #{lot_id}\nОписание: {data.get('description')}\nЦена: {data['price']} ₽\nПродавец: {get_user_contact(user_id)}",
            reply_markup=kb.as_markup()
        )
    log_action(user_id, 'CREATE_RESALE_LOT', f'Лот #{lot_id}')
    await state.clear()

@router.message(F.text == "🏷 Мои объявления")
async def my_resale_lots(message: Message):
    user_id = message.from_user.id
    if not has_role(user_id, 'reseller'):
        await message.answer("Доступно только перекупам.")
        return
    if is_user_blocked(user_id):
        await message.answer("⛔ Ваш аккаунт заблокирован.")
        return
    lots = get_active_resale_lots()
    my_lots = [lot for lot in lots if lot[1] == user_id]
    if not my_lots:
        await message.answer("У вас нет активных объявлений.")
        return
    for lot in my_lots:
        (lot_id, reseller_id, category_id, brand_id, model_id, specs, description, condition,
         photo_file_ids, video_file_id, price,
         battery_cycles, max_capacity, display_replaced, defects, accessories,
         views, offers_count, reserve_count, created_at, status) = lot
        photo_list = photo_file_ids.split(',') if photo_file_ids else []
        photo_id = photo_list[0] if photo_list else None
        caption = (
            f"🔹 Объявление #{lot_id}\n"
            f"Описание: {description}\n"
            f"Состояние: {condition}\n"
            f"Циклов: {battery_cycles}\n"
            f"Ёмкость: {max_capacity}%\n"
            f"Дисплей: {display_replaced}\n"
            f"Дефекты: {defects}\n"
            f"Комплект: {accessories}\n"
            f"Цена: {price} ₽\n"
            f"Просмотров: {views}\n"
            f"Предложений: {offers_count}\n"
            f"Резервов: {reserve_count}\n"
            f"Статус: {status}\n"
            f"Создано: {created_at}\n"
        )
        if photo_id:
            await message.answer_photo(photo=photo_id, caption=caption)
        else:
            await message.answer(caption)

@router.message(F.text == "📊 Моя статистика")
async def my_stats(message: Message):
    user_id = message.from_user.id
    if not has_role(user_id, 'reseller'):
        await message.answer("Доступно только перекупам.")
        return
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('''
        SELECT COUNT(*), SUM(price) FROM resale_lots 
        WHERE reseller_id = ? AND status = 'sold'
    ''', (user_id,))
    sold_count, sold_sum = cur.fetchone()
    cur.execute('''
        SELECT COUNT(*) FROM resale_lots WHERE reseller_id = ? AND status = 'active'
    ''', (user_id,))
    active_count = cur.fetchone()[0]
    cur.execute('''
        SELECT AVG(rating) FROM reviews WHERE seller_id = ?
    ''', (user_id,))
    avg_rating = cur.fetchone()[0]
    conn.close()
    text = (
        f"📊 Ваша статистика:\n\n"
        f"✅ Продано лотов: {sold_count or 0}\n"
        f"💰 Общая выручка: {sold_sum or 0} ₽\n"
        f"📦 Активных объявлений: {active_count}\n"
        f"⭐ Средний рейтинг: {round(avg_rating, 2) if avg_rating else 'нет отзывов'}\n"
    )
    await message.answer(text)

@router.callback_query(F.data.startswith("confirm_sale_"))
async def confirm_sale_handler(callback: CallbackQuery, **kwargs):
    user_id = callback.from_user.id
    lot_id = int(callback.data.split("_")[2])
    lot = get_resale_lot_by_id(lot_id)
    if not lot or lot[19] != 'reserved':  # status
        await callback.answer("Лот не в статусе резерва.", show_alert=True)
        return
    if lot[1] != user_id:
        await callback.answer("Это не ваше объявление.", show_alert=True)
        return
    if confirm_sale(lot_id):
        update_reliability(user_id, 2)
        buyer_id = lot[20]  # buyer_id
        if buyer_id:
            await callback.bot.send_message(
                buyer_id,
                f"✅ Продавец подтвердил сделку по товару #{lot_id}!\n"
                f"Свяжитесь с ним: {get_user_contact(user_id)}"
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
                update_balance(referrer_id, 1000)
                mark_reward_given(referral_id, 1000)
                await callback.bot.send_message(
                    referrer_id,
                    f"🎉 Ваш реферал совершил первую покупку! Вам начислено 1000 баллов."
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
    user_id = callback.from_user.id
    lot_id = int(callback.data.split("_")[2])
    lot = get_resale_lot_by_id(lot_id)
    if not lot or lot[19] != 'reserved':
        await callback.answer("Лот не в статусе резерва.", show_alert=True)
        return
    if lot[1] != user_id:
        await callback.answer("Это не ваше объявление.", show_alert=True)
        return
    if cancel_reserve(lot_id):
        update_reliability(user_id, -5)
        rating = get_user_reliability(user_id)
        if rating < 50:
            block_user(user_id, 24)
            await callback.bot.send_message(
                user_id,
                "⛔ Ваш рейтинг надёжности слишком низок. Вы заблокированы на 24 часа."
            )
        buyer_id = lot[20]
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

@router.message(Command("accept_offer"))
async def accept_offer(message: Message, state: FSMContext):
    args = message.text.split()
    if len(args) != 2:
        await message.answer("Использование: /accept_offer <id_предложения>")
        return
    try:
        offer_id = int(args[1])
    except:
        await message.answer("Неверный ID предложения.")
        return
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('SELECT lot_id, buyer_id, price FROM price_offers WHERE id = ? AND status = "pending"', (offer_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        await message.answer("Предложение не найдено или уже обработано.")
        return
    lot_id, buyer_id, price = row
    lot = get_resale_lot_by_id(lot_id)
    if not lot or lot[1] != message.from_user.id:
        await message.answer("Это не ваш лот.")
        return
    if reserve_lot(lot_id, buyer_id):
        update_price_offer_status(offer_id, 'accepted')
        await message.answer(f"✅ Предложение {price} ₽ принято. Товар зарезервирован за покупателем.")
        await message.bot.send_message(
            buyer_id,
            f"✅ Ваше предложение {price} ₽ на лот #{lot_id} принято! Продавец свяжется с вами."
        )
        log_action(message.from_user.id, 'ACCEPT_OFFER', f'Предложение #{offer_id}, лот #{lot_id}')
    else:
        await message.answer("Ошибка при резервировании лота.")

@router.message(Command("reject_offer"))
async def reject_offer(message: Message):
    args = message.text.split()
    if len(args) != 2:
        await message.answer("Использование: /reject_offer <id_предложения>")
        return
    try:
        offer_id = int(args[1])
    except:
        await message.answer("Неверный ID предложения.")
        return
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    cur.execute('SELECT lot_id, buyer_id FROM price_offers WHERE id = ? AND status = "pending"', (offer_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        await message.answer("Предложение не найдено или уже обработано.")
        return
    lot_id, buyer_id = row
    lot = get_resale_lot_by_id(lot_id)
    if not lot or lot[1] != message.from_user.id:
        await message.answer("Это не ваш лот.")
        return
    update_price_offer_status(offer_id, 'rejected')
    await message.answer(f"❌ Предложение отклонено.")
    await message.bot.send_message(
        buyer_id,
        f"❌ Ваше предложение на лот #{lot_id} отклонено продавцом."
    )
    log_action(message.from_user.id, 'REJECT_OFFER', f'Предложение #{offer_id}, лот #{lot_id}')

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
    if is_user_blocked(user_id):
        await message.answer("⛔ Ваш аккаунт заблокирован.")
        return
    subs = get_user_subscriptions(user_id)
    await state.update_data(subs=subs)
    await message.answer(
        "Управление подписками. Выберите категорию для настройки:",
        reply_markup=subscriptions_multiselect_keyboard(subs)
    )
    await state.set_state(SubscriptionState.selecting)

@router.callback_query(SubscriptionState.selecting, F.data.startswith("sub_settings_"))
async def sub_settings(callback: CallbackQuery, state: FSMContext):
    cat_part = callback.data.replace("sub_settings_", "")
    if cat_part == "all":
        cat_id = None
    else:
        cat_id = int(cat_part)
    data = await state.get_data()
    subs = data.get('subs', [])
    current = next((s for s in subs if s[0] == cat_id), (cat_id, False, False, False))
    await state.update_data(current_cat=cat_id, current_settings=current)
    await callback.message.edit_text(
        f"Настройки для {'всех категорий' if cat_id is None else f'категории ID {cat_id}'}",
        reply_markup=subscription_settings_keyboard(cat_id, current)
    )
    await state.set_state(SubscriptionState.category_settings)
    await callback.answer()

@router.callback_query(SubscriptionState.category_settings, F.data.startswith("sub_toggle_"))
async def sub_toggle(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    toggle_type = parts[2]
    cat_part = parts[3]
    if cat_part == "all":
        cat_id = None
    else:
        cat_id = int(cat_part)
    data = await state.get_data()
    subs = data.get('subs', [])
    current = next((s for s in subs if s[0] == cat_id), (cat_id, False, False, False))
    new_flags = list(current[1:4])
    if toggle_type == "new":
        new_flags[0] = not new_flags[0]
    elif toggle_type == "price":
        new_flags[1] = not new_flags[1]
    elif toggle_type == "end":
        new_flags[2] = not new_flags[2]
    subs = [s for s in subs if s[0] != cat_id]
    subs.append((cat_id, new_flags[0], new_flags[1], new_flags[2]))
    await state.update_data(subs=subs)
    await callback.message.edit_reply_markup(
        reply_markup=subscription_settings_keyboard(cat_id, (cat_id, new_flags[0], new_flags[1], new_flags[2]))
    )
    await callback.answer()

@router.callback_query(SubscriptionState.category_settings, F.data == "sub_back")
async def sub_back(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    subs = data.get('subs', [])
    await callback.message.edit_text(
        "Управление подписками. Выберите категорию для настройки:",
        reply_markup=subscriptions_multiselect_keyboard(subs)
    )
    await state.set_state(SubscriptionState.selecting)
    await callback.answer()

@router.callback_query(SubscriptionState.selecting, F.data == "sub_save")
async def sub_save(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    data = await state.get_data()
    subs = data.get('subs', [])
    unsubscribe_user(user_id)
    for s in subs:
        cat_id, new_flag, price_flag, end_flag = s
        subscribe_user(user_id, cat_id, new_flag, price_flag, end_flag)
    await callback.message.answer("✅ Подписки обновлены!")
    await callback.message.delete()
    await state.clear()

@router.message(F.text == "⭐ Избранное")
async def show_favorites(message: Message):
    user_id = message.from_user.id
    if not user_exists(user_id):
        await message.answer("Сначала зарегистрируйтесь.")
        return
    from database import get_user_favorites, get_resale_lot_by_id, get_seller_rating
    favorites = get_user_favorites(user_id)
    if not favorites:
        await message.answer("У вас пока нет избранных объявлений.")
        return
    for fav in favorites:
        lot_id, price_at_add, created_at, current_price, description = fav
        lot = get_resale_lot_by_id(lot_id)
        if not lot:
            continue
        seller_id = lot[1]
        seller_contact = get_user_contact(seller_id)
        rating, count = get_seller_rating(seller_id)
        rating_text = f"⭐ {rating} ({count} отзывов)" if rating else "⭐ нет отзывов"
        caption = (
            f"⭐ В избранном с {created_at}\n"
            f"Цена тогда: {price_at_add} ₽, сейчас: {current_price} ₽\n"
            f"📝 {description}\n"
            f"👤 Продавец: {seller_contact} {rating_text}"
        )
        photo_list = lot[8].split(',') if lot[8] else []
        photo_id = photo_list[0] if photo_list else None
        if photo_id:
            await message.answer_photo(photo=photo_id, caption=caption)
        else:
            await message.answer(caption)

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
        f"Приглашайте друзей! Когда они зарегистрируются и совершат первую покупку, вы получите 1000 баллов.\n"
        f"Баллы можно использовать для оплаты статуса перекупа (5000 баллов) и других услуг."
    )
    await message.answer(text)

@router.message(F.text == "💰 Мой кошелек")
async def reseller_wallet(message: Message):
    await show_wallet(message)