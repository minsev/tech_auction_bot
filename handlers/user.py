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
    encode_referrer_id
)
from keyboards import (
    user_menu, categories_inline_keyboard, brands_inline_keyboard,
    models_inline_keyboard, specs_multiselect_keyboard,
    my_request_inline_keyboard, offers_inline_keyboard,
    subscriptions_multiselect_keyboard
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

class SubscriptionState(StatesGroup):
    selecting = State()

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
        data = await state.get_data()
        user_id = message.from_user.id

        category_id = data.get('category_id')
        brand_id = data.get('brand_id', 0)
        model_id = data.get('model_id', 0)
        specs = data.get('specs', '')
        description = data.get('description', '')
        condition = data.get('condition', '')
        photo = data.get('photo', '')

        req_id = create_buyout_request(
            user_id=user_id,
            category_id=category_id,
            brand_id=brand_id,
            model_id=model_id,
            specs=specs,
            description=description,
            condition=condition,
            photo_file_id=photo,
            desired_price=price
        )
        await message.answer(
            f"✅ Заявка #{req_id} создана! Перекупы уже видят её.\n"
            f"Следите за предложениями в разделе «📋 Мои заявки».",
            reply_markup=user_menu()
        )
        await state.clear()
    except ValueError:
        await message.answer("Введите целое число (например, 5000).")

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
        req_id, category_id, brand_id, model_id, specs, description, condition, photo_id, desired_price, status, created_at = req
        caption = (
            f"🔹 Заявка #{req_id}\n"
            f"Описание: {description}\n"
            f"Состояние: {condition}\n"
            f"Желаемая цена: {desired_price} ₽\n"
            f"Статус: {status}\n"
            f"Создано: {created_at}\n"
        )
        await message.answer_photo(
            photo=photo_id,
            caption=caption,
            reply_markup=my_request_inline_keyboard(req_id) if status == 'active' else None
        )

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
        text += f"\n{price} ₽ от {reseller_name}"
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
        # Toggle all
        if None in selected:
            selected.remove(None)
        else:
            selected = [None]  # None означает все категории
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
    # Очищаем старые подписки
    unsubscribe_user(user_id)  # удаляем все
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
async def user_wallet(message: Message):
    await show_wallet(message)