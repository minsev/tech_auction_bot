from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import (
    has_role, user_exists, get_categories,
    get_brands_by_category, get_models_by_brand, get_specs_by_model,
    create_buyout_request, get_user_buyout_requests, get_buyout_request_by_id,
    get_offers_for_request, complete_buyout_request, cancel_buyout_request, get_user_info,
    subscribe_user, unsubscribe_user, get_user_subscriptions, get_user_balance,
    encode_referrer_id, add_favorite, remove_favorite, is_favorite, get_user_favorites,
    log_action, get_user_contact, get_resale_lot_by_id, increment_lot_views,
    get_seller_rating
)
from keyboards import (
    user_menu, categories_inline_keyboard, brands_inline_keyboard,
    models_inline_keyboard, specs_multiselect_keyboard,
    my_request_inline_keyboard, offers_inline_keyboard,
    subscriptions_multiselect_keyboard, subscription_settings_keyboard,
    resale_lot_inline_keyboard
)
from handlers.payment import show_wallet

router = Router()

class BuyoutRequestCreation(StatesGroup):
    category = State()
    brand = State()
    model = State()
    specs = State()
    custom_description = State()
    custom_condition = State()
    custom_photo = State()
    custom_price = State()
    use_custom = State()
    battery_cycles = State()
    max_capacity = State()
    display_replaced = State()
    defects = State()
    accessories = State()

class SubscriptionState(StatesGroup):
    selecting = State()
    category_settings = State()

@router.message(F.text == "💰 Срочный выкуп")
async def user_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not user_exists(user_id):
        await message.answer("Сначала зарегистрируйтесь через /start.")
        return
    if not has_role(user_id, 'user'):
        await message.answer("У вас нет прав пользователя.")
        return
    await message.answer("Выберите действие:", reply_markup=user_menu())

# ---------- Создание заявки на выкуп ----------
@router.message(F.text == "💰 Создать заявку на выкуп")
async def create_request_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not user_exists(user_id) or not has_role(user_id, 'user'):
        await message.answer("Сначала зарегистрируйтесь как пользователь.")
        return
    await message.answer(
        "Выберите категорию товара:",
        reply_markup=categories_inline_keyboard()
    )
    await state.set_state(BuyoutRequestCreation.category)

@router.callback_query(BuyoutRequestCreation.category, F.data.startswith("cat_"))
async def req_category_chosen(callback: CallbackQuery, state: FSMContext):
    category_id = int(callback.data.split("_")[1])
    await state.update_data(category_id=category_id)
    brands = get_brands_by_category(category_id)
    if brands:
        await callback.message.delete()
        await callback.message.answer(
            "Выберите бренд:",
            reply_markup=brands_inline_keyboard(category_id)
        )
        await state.set_state(BuyoutRequestCreation.brand)
        await state.update_data(use_custom=False)
    else:
        await state.update_data(use_custom=True)
        await callback.message.delete()
        await callback.message.answer("Введите название бренда (или модель) вручную:")
        await state.set_state(BuyoutRequestCreation.custom_description)
    await callback.answer()

@router.callback_query(BuyoutRequestCreation.brand, F.data.startswith("brand_"))
async def req_brand_chosen(callback: CallbackQuery, state: FSMContext):
    brand_id = int(callback.data.split("_")[1])
    await state.update_data(brand_id=brand_id)
    models = get_models_by_brand(brand_id)
    if models:
        await callback.message.delete()
        await callback.message.answer(
            "Выберите модель:",
            reply_markup=models_inline_keyboard(brand_id)
        )
        await state.set_state(BuyoutRequestCreation.model)
    else:
        await state.update_data(use_custom=True)
        await callback.message.delete()
        await callback.message.answer("Введите описание товара (обязательно):")
        await state.set_state(BuyoutRequestCreation.custom_description)
    await callback.answer()

@router.callback_query(BuyoutRequestCreation.model, F.data.startswith("model_"))
async def req_model_chosen(callback: CallbackQuery, state: FSMContext):
    model_id = int(callback.data.split("_")[1])
    await state.update_data(model_id=model_id, selected_specs=[])
    specs = get_specs_by_model(model_id)
    if specs:
        await callback.message.delete()
        await callback.message.answer(
            "Выберите характеристики (можно несколько):",
            reply_markup=specs_multiselect_keyboard(model_id, [])
        )
        await state.set_state(BuyoutRequestCreation.specs)
    else:
        await state.update_data(use_custom=True)
        await callback.message.delete()
        await callback.message.answer("Введите описание товара (обязательно):")
        await state.set_state(BuyoutRequestCreation.custom_description)
    await callback.answer()

@router.callback_query(BuyoutRequestCreation.specs, F.data.startswith("spec_"))
async def spec_toggle(callback: CallbackQuery, state: FSMContext):
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

@router.callback_query(BuyoutRequestCreation.specs, F.data == "specs_done")
async def specs_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get('selected_specs', [])
    if not selected:
        await callback.answer("Выберите хотя бы одну характеристику", show_alert=True)
        return
    specs_str = ','.join(str(s) for s in selected)
    await state.update_data(specs=specs_str)
    await callback.message.delete()
    await callback.message.answer("Введите дополнительное описание (или отправьте '-' если не требуется):")
    await state.set_state(BuyoutRequestCreation.custom_description)
    await callback.answer()

@router.message(BuyoutRequestCreation.custom_description)
async def req_custom_description(message: Message, state: FSMContext):
    desc = message.text.strip() if message.text else ""
    if desc == '-':
        desc = ""
    await state.update_data(description=desc)
    await message.answer("Введите состояние товара (новое, б/у, как новое, требуется ремонт) (обязательно):")
    await state.set_state(BuyoutRequestCreation.custom_condition)

@router.message(BuyoutRequestCreation.custom_condition)
async def req_custom_condition(message: Message, state: FSMContext):
    if not message.text or not message.text.strip():
        await message.answer("Состояние не может быть пустым. Введите состояние:")
        return
    await state.update_data(condition=message.text.strip())
    await message.answer("Загрузите фото товара (обязательно):")
    await state.set_state(BuyoutRequestCreation.custom_photo)

@router.message(BuyoutRequestCreation.custom_photo, F.photo)
async def req_custom_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo=photo_id)
    await message.answer("Введите желаемую цену в рублях (только число, обязательно):")
    await state.set_state(BuyoutRequestCreation.custom_price)

@router.message(BuyoutRequestCreation.custom_photo)
async def req_custom_photo_invalid(message: Message):
    await message.answer("Пожалуйста, загрузите фото (не текст).")

@router.message(BuyoutRequestCreation.custom_price)
async def req_custom_price(message: Message, state: FSMContext):
    try:
        cleaned = message.text.strip().replace(' ', '').replace(',', '')
        price = int(cleaned)
        if price <= 0:
            await message.answer("Цена должна быть положительным числом. Введите цену:")
            return
        await state.update_data(desired_price=price)
        await message.answer("Введите количество циклов перезарядки (если известно, иначе 0):")
        await state.set_state(BuyoutRequestCreation.battery_cycles)
    except ValueError:
        await message.answer("Введите целое число (например, 5000).")

@router.message(BuyoutRequestCreation.battery_cycles)
async def req_battery_cycles(message: Message, state: FSMContext):
    try:
        cycles = int(message.text.strip())
        await state.update_data(battery_cycles=cycles)
        await message.answer("Введите максимальную ёмкость аккумулятора в % (например, 85):")
        await state.set_state(BuyoutRequestCreation.max_capacity)
    except ValueError:
        await message.answer("Введите целое число.")

@router.message(BuyoutRequestCreation.max_capacity)
async def req_max_capacity(message: Message, state: FSMContext):
    try:
        capacity = int(message.text.strip())
        await state.update_data(max_capacity=capacity)
        await message.answer("Был ли переклеен дисплей? (Да/Нет):")
        await state.set_state(BuyoutRequestCreation.display_replaced)
    except ValueError:
        await message.answer("Введите целое число.")

@router.message(BuyoutRequestCreation.display_replaced)
async def req_display_replaced(message: Message, state: FSMContext):
    text = message.text.strip().lower()
    if text in ['да', 'нет']:
        await state.update_data(display_replaced=text)
        await message.answer("Опишите дефекты (если есть, иначе '-'):")
        await state.set_state(BuyoutRequestCreation.defects)
    else:
        await message.answer("Введите 'Да' или 'Нет'.")

@router.message(BuyoutRequestCreation.defects)
async def req_defects(message: Message, state: FSMContext):
    defects = message.text.strip()
    if defects == '-':
        defects = ''
    await state.update_data(defects=defects)
    await message.answer("Что входит в комплект? (перечислите через запятую или '-' если ничего):")
    await state.set_state(BuyoutRequestCreation.accessories)

@router.message(BuyoutRequestCreation.accessories)
async def req_accessories(message: Message, state: FSMContext):
    accessories = message.text.strip()
    if accessories == '-':
        accessories = ''
    data = await state.get_data()
    user_id = message.from_user.id

    req_id = create_buyout_request(
        user_id=user_id,
        category_id=data['category_id'],
        brand_id=data.get('brand_id', 0),
        model_id=data.get('model_id', 0),
        specs=data.get('specs', ''),
        description=data.get('description', ''),
        condition=data.get('condition', ''),
        photo_file_ids=[data['photo']],
        video_file_id=None,
        desired_price=data['desired_price'],
        battery_cycles=data.get('battery_cycles'),
        max_capacity=data.get('max_capacity'),
        display_replaced=data.get('display_replaced'),
        defects=data.get('defects'),
        accessories=accessories
    )
    await message.answer(
        f"✅ Заявка #{req_id} создана! Перекупы уже видят её.\n"
        f"Следите за предложениями в разделе «📋 Мои заявки».",
        reply_markup=user_menu()
    )
    log_action(user_id, 'CREATE_BUYOUT_REQUEST', f'Заявка #{req_id}')
    await state.clear()

# ---------- Мои заявки ----------
@router.message(F.text == "📋 Мои заявки")
async def my_requests(message: Message):
    user_id = message.from_user.id
    if not user_exists(user_id) or not has_role(user_id, 'user'):
        await message.answer("Этот раздел для пользователей.")
        return
    requests = get_user_buyout_requests(user_id)
    if not requests:
        await message.answer("У вас нет заявок.")
        return
    for req in requests:
        (req_id, category_id, brand_id, model_id, specs, description, condition,
         photo_file_ids, video_file_id, desired_price,
         battery_cycles, max_capacity, display_replaced, defects, accessories,
         status, created_at) = req
        photo_list = photo_file_ids.split(',') if photo_file_ids else []
        photo_id = photo_list[0] if photo_list else None
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
            f"Статус: {status}\n"
            f"Создано: {created_at}\n"
        )
        if photo_id:
            await message.answer_photo(
                photo=photo_id,
                caption=caption,
                reply_markup=my_request_inline_keyboard(req_id) if status == 'active' else None
            )
        else:
            await message.answer(caption, reply_markup=my_request_inline_keyboard(req_id) if status == 'active' else None)

# ---------- Просмотр предложений и выбор победителя ----------
@router.callback_query(F.data.startswith("view_offers_"))
async def view_offers(callback: CallbackQuery):
    req_id = int(callback.data.split("_")[2])
    offers = get_offers_for_request(req_id)
    if not offers:
        await callback.message.answer("Пока нет предложений.")
        await callback.answer()
        return
    text = f"Предложения по заявке #{req_id}:\n"
    for offer_id, reseller_id, price, created_at in offers:
        reseller_info = get_user_info(reseller_id)
        reseller_name = reseller_info[0] if reseller_info else "Неизвестно"
        # Исправление: преобразуем строку в datetime
        dt = datetime.fromisoformat(created_at.replace(' ', 'T'))
        text += f"\n{price} ₽ от {reseller_name} ({dt.strftime('%d.%m %H:%M')})"
    await callback.message.answer(
        text,
        reply_markup=offers_inline_keyboard(offers, req_id)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("choose_offer_"))
async def choose_offer(callback: CallbackQuery):
    parts = callback.data.split("_")
    offer_id = int(parts[2])
    req_id = int(parts[3])
    
    # Проверка, что заявка принадлежит вызывающему пользователю
    req = get_buyout_request_by_id(req_id)
    if not req or req[1] != callback.from_user.id:
        await callback.answer("Это не ваша заявка", show_alert=True)
        return
    
    offers = get_offers_for_request(req_id)
    winner_id = None
    price = 0
    for o in offers:
        if o[0] == offer_id:
            winner_id = o[1]
            price = o[2]
            break
    if not winner_id:
        await callback.answer("Ошибка", show_alert=True)
        return
    complete_buyout_request(req_id, winner_id)
    await callback.message.answer(f"✅ Вы выбрали предложение {price} ₽. Контакты перекупа будут отправлены вам в личку.")
    winner_info = get_user_info(winner_id)
    winner_phone = winner_info[1] if winner_info else "не указан"
    await callback.bot.send_message(
        callback.from_user.id,
        f"Контакты перекупа: {winner_phone}"
    )
    req = get_buyout_request_by_id(req_id)
    if req:
        seller_id = req[1]
        seller_info = get_user_info(seller_id)
        seller_phone = seller_info[1] if seller_info else "не указан"
        await callback.bot.send_message(
            winner_id,
            f"🎉 Ваше предложение {price} ₽ по заявке #{req_id} принято! Свяжитесь с продавцом: {seller_phone}"
        )
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()

@router.callback_query(F.data.startswith("cancel_req_"))
async def cancel_request(callback: CallbackQuery):
    req_id = int(callback.data.split("_")[2])
    cancel_buyout_request(req_id)
    await callback.message.edit_caption(caption=callback.message.caption + "\n\n❌ Заявка отменена.")
    await callback.answer("Заявка отменена")

# ---------- История ставок ----------
@router.callback_query(F.data.startswith("history_"))
async def offer_history(callback: CallbackQuery):
    req_id = int(callback.data.split("_")[1])
    offers = get_offers_for_request(req_id)
    if not offers:
        await callback.message.answer("По этой заявке пока нет предложений.")
        await callback.answer()
        return
    text = f"📈 История ставок по заявке #{req_id}:\n\n"
    for o in offers:
        offer_id, reseller_id, price, created_at = o
        reseller_info = get_user_info(reseller_id)
        reseller_name = reseller_info[0] if reseller_info else "Неизвестно"
        # Исправление: преобразуем строку в datetime
        dt = datetime.fromisoformat(created_at.replace(' ', 'T'))
        text += f"• {price} ₽ от {reseller_name} – {dt.strftime('%d.%m %H:%M')}\n"
    await callback.message.answer(text)
    await callback.answer()

# ---------- Избранное ----------
@router.message(F.text == "⭐ Избранное")
async def show_favorites(message: Message):
    user_id = message.from_user.id
    if not user_exists(user_id):
        await message.answer("Сначала зарегистрируйтесь.")
        return
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
        await message.answer_photo(
            photo=lot[8].split(',')[0] if lot[8] else None,
            caption=caption,
            reply_markup=resale_lot_inline_keyboard(lot_id, current_price, is_favorite=True)
        )

# ---------- Подписки ----------
@router.message(F.text == "🔔 Мои подписки")
async def my_subscriptions(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not user_exists(user_id):
        await message.answer("Сначала зарегистрируйтесь.")
        return
    subs = get_user_subscriptions(user_id)  # список (category_id, notify_on_new, notify_on_price_drop, notify_on_auction_end)
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
    toggle_type = parts[2]  # new, price, end
    cat_part = parts[3]
    if cat_part == "all":
        cat_id = None
    else:
        cat_id = int(cat_part)
    data = await state.get_data()
    subs = data.get('subs', [])
    current = next((s for s in subs if s[0] == cat_id), (cat_id, False, False, False))
    # Изменяем нужный флаг
    new_flags = list(current[1:4])
    if toggle_type == "new":
        new_flags[0] = not new_flags[0]
    elif toggle_type == "price":
        new_flags[1] = not new_flags[1]
    elif toggle_type == "end":
        new_flags[2] = not new_flags[2]
    # Обновляем в списке
    subs = [s for s in subs if s[0] != cat_id]
    subs.append((cat_id, new_flags[0], new_flags[1], new_flags[2]))
    await state.update_data(subs=subs)
    # Показываем обновлённую клавиатуру
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
    # Очищаем старые подписки
    unsubscribe_user(user_id)
    for s in subs:
        cat_id, new_flag, price_flag, end_flag = s
        subscribe_user(user_id, cat_id, new_flag, price_flag, end_flag)
    await callback.message.answer("✅ Подписки обновлены!")
    await callback.message.delete()
    await state.clear()

# ---------- Реферальная программа ----------
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

# ---------- Кошелек ----------
@router.message(F.text == "💰 Мой кошелек")
async def user_wallet(message: Message):
    await show_wallet(message)
