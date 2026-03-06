import json
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import get_user_balance, update_balance, get_referrer
from keyboards import payment_keyboard
from config import PROVIDER_TOKEN, CURRENCY

router = Router()

class PaymentState(StatesGroup):
    waiting_for_payment = State()

@router.message(F.text == "💰 Мой кошелек")
async def show_wallet(message: Message):
    user_id = message.from_user.id
    balance = get_user_balance(user_id)
    
    text = (
        f"💰 Ваш баланс: **{balance} баллов**\n\n"
        f"1 балл = 1 рубль\n\n"
        f"Баллы можно использовать для:\n"
        f"• Покупки статуса перекупа (5000 баллов)\n"
        f"• (в будущем) других платных услуг\n\n"
        f"Выберите сумму пополнения:"
    )
    
    await message.answer(text, parse_mode="Markdown", reply_markup=payment_keyboard())

@router.callback_query(F.data.startswith("pay_"))
async def process_payment(callback: CallbackQuery, state: FSMContext):
    amount_str = callback.data.split("_")[1]
    amount_rub = int(amount_str)
    amount_kop = amount_rub * 100
    
    user_id = callback.from_user.id
    
    provider_data = {
        "receipt": {
            "items": [
                {
                    "description": f"Пополнение кошелька на {amount_rub} руб.",
                    "quantity": "1.00",
                    "amount": {
                        "value": f"{amount_rub}.00",
                        "currency": CURRENCY
                    },
                    "vat_code": 1
                }
            ]
        }
    }
    
    prices = [LabeledPrice(label=f"Пополнение кошелька", amount=amount_kop)]
    
    await state.set_state(PaymentState.waiting_for_payment)
    
    try:
        await callback.bot.send_invoice(
            chat_id=user_id,
            title="Пополнение кошелька",
            description=f"Пополнение баланса на {amount_rub} рублей",
            payload=f"wallet_topup_{user_id}_{amount_rub}",
            provider_token=PROVIDER_TOKEN,
            currency=CURRENCY,
            prices=prices,
            need_phone_number=False,
            send_phone_number_to_provider=False,
            need_email=False,
            send_email_to_provider=False,
            provider_data=json.dumps(provider_data),
            start_parameter="topup"
        )
    except Exception as e:
        logging.error(f"Ошибка при создании платежа: {e}")
        await callback.message.answer("Произошла ошибка при создании платежа. Попробуйте позже.")
        await state.clear()
    
    await callback.answer()

@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery, state: FSMContext):
    await pre_checkout_query.bot.answer_pre_checkout_query(
        pre_checkout_query.id,
        ok=True
    )

@router.message(F.successful_payment)
async def successful_payment_handler(message: Message, state: FSMContext):
    payment = message.successful_payment
    payload = payment.invoice_payload
    
    parts = payload.split('_')
    if len(parts) == 4 and parts[0] == 'wallet':
        user_id = int(parts[2])
        amount_rub = int(parts[3])
        
        update_balance(user_id, amount_rub)
        
        await message.answer(
            f"✅ Платеж на сумму {amount_rub} руб. успешно зачислен!\n"
            f"Ваш новый баланс: {get_user_balance(user_id)} баллов."
        )
        
        referrer_id = get_referrer(user_id)
        if referrer_id:
            bonus = int(amount_rub * 0.2)
            update_balance(referrer_id, bonus)
            try:
                await message.bot.send_message(
                    referrer_id,
                    f"🎉 Ваш реферал пополнил кошелек на {amount_rub} руб.\n"
                    f"Вам начислено {bonus} баллов (20%)."
                )
            except:
                pass
    else:
        await message.answer("Платеж получен, но не удалось обработать назначение.")
    
    await state.clear()

@router.callback_query(F.data == "back_to_wallet")
async def back_to_wallet(callback: CallbackQuery):
    await show_wallet(callback.message)
    await callback.answer()