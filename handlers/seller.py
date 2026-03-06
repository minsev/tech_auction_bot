from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import add_user, create_auction_lot, get_user_role, get_categories, get_all_admins
from keyboards import seller_menu, main_menu
from config import ADMIN_GROUP_ID

router = Router()

class SellerRegistration(StatesGroup):
    full_name = State()
    phone = State()

class AuctionLotCreation(StatesGroup):
    category = State()
    title = State()
    description = State()
    condition = State()
    photo = State()
    start_price = State()

@router.message(F.text == "🛒 Я хочу продать технику")
async def seller_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    role = get_user_role(user_id)
    if role == 'seller':
        await message.answer("Вы уже зарегистрированы как продавец.", reply_markup=seller_menu())
    elif role in ('reseller', 'buyer'):
        await message.answer(f"Вы уже зарегистрированы как {role}. Нельзя стать продавцом с тем же аккаунтом.")
    else:
        await message.answer("Регистрация продавца.\nВведите ваше ФИО:")
        await state.set_state(SellerRegistration.full_name)

@router.message(SellerRegistration.full_name)
async def seller_full_name(message: Message, state: FSMContext):
    await state.update_data(full_name=message.text)
    await message.answer("Введите ваш контактный телефон:")
    await state.set_state(SellerRegistration.phone)

@router.message(SellerRegistration.phone)
async def seller_phone(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    add_user(user_id, 'seller', message.text, data['full_name'])
    await message.answer("Регистрация завершена! Теперь вы можете создавать лоты.", reply_markup=seller_menu())
    await state.clear()

@router.message(F.text == "➕ Создать новый лот (аукцион для перекупов)")
async def create_auction_lot_start(message: Message, state: FSMContext):
    if get_user_role(message.from_user.id) != 'seller':
        await message.answer("Сначала зарегистрируйтесь как продавец.")
        return
    categories = get_categories()
    cats_str = "\n".join([f"{i+1}. {cat}" for i, cat in enumerate(categories)])
    await message.answer(f"Выберите категорию:\n{cats_str}\n\nВведите название категории из списка:")
    await state.set_state(AuctionLotCreation.category)

@router.message(AuctionLotCreation.category)
async def process_category(message: Message, state: FSMContext):
    category = message.text.strip()
    categories = get_categories()
    if category not in categories:
        await message.answer("Такой категории нет. Введите название точно из списка.")
        return
    await state.update_data(category=category)
    await message.answer("Введите название товара (модель, бренд):")
    await state.set_state(AuctionLotCreation.title)

@router.message(AuctionLotCreation.title)
async def process_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("Введите описание товара (состояние, комплектация, дефекты и т.д.):")
    await state.set_state(AuctionLotCreation.description)

@router.message(AuctionLotCreation.description)
async def process_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("Введите состояние (новое, б/у, как новое, требуется ремонт):")
    await state.set_state(AuctionLotCreation.condition)

@router.message(AuctionLotCreation.condition)
async def process_condition(message: Message, state: FSMContext):
    await state.update_data(condition=message.text)
    await message.answer("Загрузите фото товара (одно, лучшее):")
    await state.set_state(AuctionLotCreation.photo)

@router.message(AuctionLotCreation.photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo=photo_id)
    await message.answer("Введите стартовую цену (руб):")
    await state.set_state(AuctionLotCreation.start_price)

@router.message(AuctionLotCreation.start_price)
async def process_start_price(message: Message, state: FSMContext):
    try:
        start_price = int(message.text)
        data = await state.get_data()
        user_id = message.from_user.id
        expires_at = datetime.now() + timedelta(hours=24)  # аукцион на 24 часа
        
        lot_id = create_auction_lot(
            seller_id=user_id,
            category=data['category'],
            title=data['title'],
            description=data['description'],
            condition=data['condition'],
            photo_file_id=data['photo'],
            start_price=start_price,
            expires_at=expires_at
        )
        
        await message.answer(
            f"✅ Лот #{lot_id} создан и отправлен на модерацию!\n"
            f"После проверки администратором он появится в аукционе.",
            reply_markup=seller_menu()
        )
        
        # Отправляем уведомление в админскую группу с фото и кнопками
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Одобрить", callback_data=f"approve_lot_{lot_id}")
        kb.button(text="❌ Отклонить", callback_data=f"reject_lot_{lot_id}")
        kb.adjust(2)
        
        caption = (
            f"🆕 Новый лот на модерацию (продавец)!\n"
            f"ID лота: {lot_id}\n"
            f"Категория: {data['category']}\n"
            f"Товар: {data['title']}\n"
            f"Описание: {data['description']}\n"
            f"Состояние: {data['condition']}\n"
            f"Стартовая цена: {start_price} ₽\n"
            f"Продавец: {data['full_name']}, тел. {data['phone']}"
        )
        
        await message.bot.send_photo(
            chat_id=ADMIN_GROUP_ID,
            photo=data['photo'],
            caption=caption,
            reply_markup=kb.as_markup()
        )
        
        await state.clear()
    except ValueError:
        await message.answer("Пожалуйста, введите число.")