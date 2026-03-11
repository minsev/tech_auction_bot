from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import user_exists, add_user, add_role, decode_referrer_id, add_referral, has_role
from keyboards import main_menu, user_menu, reseller_menu

router = Router()

class Registration(StatesGroup):
    waiting_for_contact = State()

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    args = message.text.split()
    referrer_id = None
    if len(args) > 1:
        code = args[1]
        referrer_id = decode_referrer_id(code)
        if referrer_id:
            await state.update_data(referrer_id=referrer_id)

    if user_exists(user_id):
        if has_role(user_id, 'reseller'):
            await message.answer("Добро пожаловать, перекуп!", reply_markup=reseller_menu())
        else:
            await message.answer("Добро пожаловать!", reply_markup=user_menu())
    else:
        kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="📱 Зарегистрироваться", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await message.answer(
            "👋 Добро пожаловать! Для использования бота необходимо зарегистрироваться.\n"
            "Нажмите кнопку ниже, чтобы поделиться своим номером телефона.",
            reply_markup=kb
        )
        await state.set_state(Registration.waiting_for_contact)

@router.message(Registration.waiting_for_contact, F.contact)
async def process_contact(message: Message, state: FSMContext):
    contact = message.contact
    user_id = message.from_user.id
    username = message.from_user.username
    phone = contact.phone_number

    first_name = contact.first_name or ""
    last_name = contact.last_name or ""
    full_name = f"{first_name} {last_name}".strip()
    if not full_name:
        full_name = message.from_user.full_name or "Пользователь"

    data = await state.get_data()
    referrer_id = data.get('referrer_id')

    add_user(user_id, username, phone, full_name, referrer_id)
    add_role(user_id, 'user')

    if referrer_id:
        add_referral(referrer_id, user_id)

    await message.answer(
        f"✅ Регистрация завершена, {full_name}!",
        reply_markup=user_menu()
    )
    await state.clear()

@router.message(Registration.waiting_for_contact)
async def process_contact_invalid(message: Message):
    await message.answer("Пожалуйста, нажмите кнопку «Зарегистрироваться» и отправьте свой контакт.")

@router.message(F.text == "🔙 Главное меню")
async def back_to_main(message: Message):
    await message.answer("Главное меню:", reply_markup=main_menu())

@router.message(F.text == "❓ Помощь")
async def help_cmd(message: Message):
    await message.answer(
        "**Помощь**\n\n"
        "**Обычный пользователь:**\n"
        "• Нажмите «💰 Срочный выкуп» и создайте заявку.\n"
        "• Перекупы увидят её и предложат цену.\n"
        "• В разделе «📋 Мои заявки» выберите лучшее предложение.\n"
        "• В разделе «🛍 Купить технику» можно купить товары у перекупов.\n"
        "• В разделе «🔔 Мои подписки» настройте уведомления о новых лотах.\n"
        "• В разделе «💸 Реферальная программа» получите ссылку для приглашения друзей.\n\n"
        "**Перекуп:**\n"
        "• Подайте заявку через «🔄 Я перекуп», после одобрения админом получите доступ.\n"
        "• В разделе «📦 Заявки на выкуп» делайте предложения.\n"
        "• В разделе «🏷 Мои объявления» создавайте и управляйте продажей техники.\n"
        "• В разделе «🛍 Купить технику» тоже можно покупать.\n"
        "• В разделе «🔔 Мои подписки» настройте уведомления о новых лотах.\n"
        "• В разделе «💸 Реферальная программа» получите ссылку для приглашения друзей.",
        parse_mode="Markdown"
    )