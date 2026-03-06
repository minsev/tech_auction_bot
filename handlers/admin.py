from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import (
    is_admin, get_all_requests, get_request, add_role, delete_request, add_admin,
    get_moderation_resale_lots, approve_resale_lot, reject_resale_lot, get_user_contact,
    get_user_balance, update_balance, get_pending_referral_by_referred, mark_reward_given
)
from config import ADMIN_GROUP_ID

router = Router()

def admin_group_only(func):
    async def wrapper(message: Message, *args, **kwargs):
        if message.chat.id != ADMIN_GROUP_ID:
            return
        return await func(message, *args, **kwargs)
    return wrapper

@router.message(Command("requests"))
@admin_group_only
async def show_requests(message: Message, **kwargs):
    requests = get_all_requests()
    if not requests:
        await message.answer("Нет заявок.")
        return
    for user_id, username, full_name, phone, created_at in requests:
        balance = get_user_balance(user_id)
        text = f"📋 Заявка на статус перекупа\nID: {user_id}\nUsername: @{username if username else 'нет'}\nИмя: {full_name}\nТелефон: {phone}\nБаланс: {balance} баллов\nДата: {created_at}"
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Платно", callback_data=f"approve_reseller_paid_{user_id}")
        kb.button(text="✅ Бесплатно", callback_data=f"approve_reseller_free_{user_id}")
        kb.button(text="❌ Отклонить", callback_data=f"reject_reseller_{user_id}")
        kb.adjust(2)
        await message.answer(text, reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("approve_reseller_paid_"))
async def approve_reseller_paid(callback: CallbackQuery, **kwargs):
    await approve_reseller(callback, paid=True)

@router.callback_query(F.data.startswith("approve_reseller_free_"))
async def approve_reseller_free(callback: CallbackQuery, **kwargs):
    await approve_reseller(callback, paid=False)

async def approve_reseller(callback: CallbackQuery, paid: bool = True):
    if callback.message.chat.id != ADMIN_GROUP_ID:
        await callback.answer("Неверный чат", show_alert=True)
        return
    user_id = int(callback.data.split("_")[-1])
    req = get_request(user_id)
    if not req:
        await callback.answer("Заявка не найдена", show_alert=True)
        return
    full_name, phone, username = req
    
    if paid:
        balance = get_user_balance(user_id)
        if balance < 5000:
            await callback.answer(f"❌ Недостаточно средств. Нужно 5000, у пользователя {balance}.", show_alert=True)
            return
        update_balance(user_id, -5000)
        ref = get_pending_referral_by_referred(user_id)
        if ref:
            referral_id, referrer_id = ref
            update_balance(referrer_id, 1000)
            mark_reward_given(referral_id, 1000)
            try:
                await callback.bot.send_message(referrer_id, f"🎉 Ваш реферал {full_name} приобрёл статус перекупа! Вам начислено 1000 баллов.")
            except:
                pass
        msg = f"✅ Перекуп {full_name} (ID {user_id}) одобрен. С баланса списано 5000 баллов."
    else:
        msg = f"✅ Перекуп {full_name} (ID {user_id}) одобрен бесплатно (администратором)."
    
    add_role(user_id, 'reseller')
    delete_request(user_id)
    
    await callback.message.edit_text(msg)
    await callback.bot.send_message(
        user_id,
        "✅ Ваша заявка на статус перекупа одобрена! Теперь вы можете участвовать." +
        (" С вашего баланса списано 5000 баллов." if paid else " (бесплатно).")
    )
    await callback.answer()

@router.callback_query(F.data.startswith("reject_reseller_"))
async def reject_reseller(callback: CallbackQuery, **kwargs):
    if callback.message.chat.id != ADMIN_GROUP_ID:
        await callback.answer("Неверный чат", show_alert=True)
        return
    user_id = int(callback.data.split("_")[2])
    delete_request(user_id)
    await callback.message.edit_text(f"❌ Заявка от {user_id} отклонена.")
    await callback.bot.send_message(user_id, "❌ Ваша заявка отклонена.")
    await callback.answer()

@router.message(Command("moderate_lots"))
@admin_group_only
async def show_moderation_lots(message: Message, **kwargs):
    lots = get_moderation_resale_lots()
    if not lots:
        await message.answer("Нет объявлений на модерации.")
        return
    for lot in lots:
        lot_id, reseller_id, category_id, brand_id, model_id, specs, description, condition, photo_id, price, created_at = lot
        seller_contact = get_user_contact(reseller_id)
        caption = (
            f"🆕 Объявление #{lot_id} на модерации\n"
            f"Описание: {description}\n"
            f"Состояние: {condition}\n"
            f"Цена: {price} ₽\n"
            f"Продавец: {seller_contact}\n"
            f"Создано: {created_at}"
        )
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Одобрить", callback_data=f"approve_lot_{lot_id}")
        kb.button(text="❌ Отклонить", callback_data=f"reject_lot_{lot_id}")
        kb.adjust(2)
        await message.answer_photo(photo=photo_id, caption=caption, reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("approve_lot_"))
async def approve_lot(callback: CallbackQuery, **kwargs):
    if callback.message.chat.id != ADMIN_GROUP_ID:
        await callback.answer("Неверный чат", show_alert=True)
        return
    lot_id = int(callback.data.split("_")[2])
    if approve_resale_lot(lot_id):
        await callback.message.edit_caption(
            callback.message.caption + "\n\n✅ Объявление одобрено и опубликовано."
        )
        from handlers.notifications import notify_new_lot
        await notify_new_lot(callback.bot, lot_id)
        await callback.answer("Объявление одобрено!")
    else:
        await callback.answer("Ошибка одобрения.", show_alert=True)

@router.callback_query(F.data.startswith("reject_lot_"))
async def reject_lot(callback: CallbackQuery, **kwargs):
    if callback.message.chat.id != ADMIN_GROUP_ID:
        await callback.answer("Неверный чат", show_alert=True)
        return
    lot_id = int(callback.data.split("_")[2])
    if reject_resale_lot(lot_id):
        await callback.message.edit_caption(
            callback.message.caption + "\n\n❌ Объявление отклонено."
        )
        await callback.answer("Объявление отклонено!")
    else:
        await callback.answer("Ошибка отклонения.", show_alert=True)

@router.message(Command("add_admin"))
@admin_group_only
async def add_admin_cmd(message: Message, **kwargs):
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет прав.")
        return
    args = message.text.split()
    if len(args) != 2:
        await message.answer("Использование: /add_admin <user_id>")
        return
    try:
        new_admin_id = int(args[1])
        add_admin(new_admin_id)
        await message.answer(f"Пользователь {new_admin_id} добавлен в администраторы.")
    except:
        await message.answer("Ошибка. Укажите числовой ID.")