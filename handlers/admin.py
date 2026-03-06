import sqlite3
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import (
    is_admin, get_all_requests, get_request, add_role, delete_request, add_admin,
    get_moderation_resale_lots, approve_resale_lot, reject_resale_lot, get_user_contact,
    get_user_balance, update_balance, get_pending_referral_by_referred, mark_reward_given,
    get_pending_complaints, resolve_complaint, get_logs, log_action
)
from config import ADMIN_GROUP_ID

router = Router()

def admin_group_only(func):
    async def wrapper(message: Message, *args, **kwargs):
        if message.chat.id != ADMIN_GROUP_ID:
            return
        return await func(message, *args, **kwargs)
    return wrapper

# ----------------- Заявки перекупов -----------------
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
    log_action(user_id, 'APPROVE_RESELLER', f'Одобрен, платно={paid}')
    
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
    log_action(user_id, 'REJECT_RESELLER', 'Заявка отклонена')
    await callback.message.edit_text(f"❌ Заявка от {user_id} отклонена.")
    await callback.bot.send_message(user_id, "❌ Ваша заявка отклонена.")
    await callback.answer()

# ----------------- Модерация объявлений -----------------
@router.message(Command("moderate_lots"))
@admin_group_only
async def show_moderation_lots(message: Message, **kwargs):
    lots = get_moderation_resale_lots()
    if not lots:
        await message.answer("Нет объявлений на модерации.")
        return
    for lot in lots:
        (lot_id, reseller_id, category_id, brand_id, model_id, specs, description, condition,
         photo_file_ids, video_file_id, price,
         battery_cycles, max_capacity, display_replaced, defects, accessories, created_at) = lot
        seller_contact = get_user_contact(reseller_id)
        photo_list = photo_file_ids.split(',') if photo_file_ids else []
        photo_id = photo_list[0] if photo_list else None
        caption = (
            f"🆕 Объявление #{lot_id} на модерации\n"
            f"Описание: {description}\n"
            f"Состояние: {condition}\n"
            f"Циклов: {battery_cycles}\n"
            f"Ёмкость: {max_capacity}%\n"
            f"Дисплей: {display_replaced}\n"
            f"Дефекты: {defects}\n"
            f"Комплект: {accessories}\n"
            f"Цена: {price} ₽\n"
            f"Продавец: {seller_contact}\n"
            f"Создано: {created_at}"
        )
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Одобрить", callback_data=f"approve_lot_{lot_id}")
        kb.button(text="❌ Отклонить", callback_data=f"reject_lot_{lot_id}")
        kb.adjust(2)
        if photo_id:
            await message.answer_photo(photo=photo_id, caption=caption, reply_markup=kb.as_markup())
        else:
            await message.answer(caption, reply_markup=kb.as_markup())

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
        log_action(0, 'APPROVE_LOT', f'Лот #{lot_id}')
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
        log_action(0, 'REJECT_LOT', f'Лот #{lot_id}')
        await callback.answer("Объявление отклонено!")
    else:
        await callback.answer("Ошибка отклонения.", show_alert=True)

# ----------------- Статистика -----------------
@router.message(Command("stats"))
@admin_group_only
async def admin_stats(message: Message, **kwargs):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    
    cur.execute('SELECT COUNT(*) FROM users')
    total_users = cur.fetchone()[0]
    
    cur.execute('SELECT COUNT(*) FROM user_roles WHERE role = "reseller"')
    total_resellers = cur.fetchone()[0]
    
    cur.execute('SELECT COUNT(*) FROM buyout_requests WHERE status = "active"')
    active_requests = cur.fetchone()[0]
    
    cur.execute('SELECT COUNT(*) FROM buyout_requests WHERE status = "completed"')
    completed_requests = cur.fetchone()[0]
    
    cur.execute('SELECT COUNT(*) FROM buyout_requests WHERE status = "expired"')
    expired_requests = cur.fetchone()[0]
    
    cur.execute('SELECT COUNT(*) FROM resale_lots WHERE status = "active"')
    active_lots = cur.fetchone()[0]
    
    cur.execute('SELECT COUNT(*) FROM resale_lots WHERE status = "sold"')
    sold_lots = cur.fetchone()[0]
    
    cur.execute('SELECT SUM(price) FROM resale_lots WHERE status = "sold"')
    total_sales = cur.fetchone()[0] or 0
    
    cur.execute('''
        SELECT c.name, COUNT(*) as cnt 
        FROM resale_lots l 
        JOIN categories c ON l.category_id = c.id 
        WHERE l.status = 'sold' 
        GROUP BY l.category_id 
        ORDER BY cnt DESC 
        LIMIT 5
    ''')
    popular_cats = cur.fetchall()
    
    conn.close()
    
    text = (
        f"📊 **Статистика бота**\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"🔄 Перекупов: {total_resellers}\n"
        f"📦 Активных заявок: {active_requests}\n"
        f"✅ Завершённых заявок: {completed_requests}\n"
        f"⏰ Истекших заявок: {expired_requests}\n"
        f"🛍 Активных объявлений: {active_lots}\n"
        f"💵 Продано лотов: {sold_lots}\n"
        f"💰 Общая выручка: {total_sales} ₽\n\n"
        f"🔥 Популярные категории:\n"
    )
    for name, cnt in popular_cats:
        text += f"   • {name}: {cnt} продаж\n"
    
    await message.answer(text, parse_mode="Markdown")

# ----------------- Жалобы -----------------
@router.message(Command("complaints"))
@admin_group_only
async def show_complaints(message: Message, **kwargs):
    complaints = get_pending_complaints()
    if not complaints:
        await message.answer("Нет новых жалоб.")
        return
    for cid, lot_id, reason, created, username, full_name in complaints:
        text = f"⚠️ Жалоба #{cid}\nЛот #{lot_id}\nОт: @{username} {full_name}\nПричина: {reason}\nСоздано: {created}"
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Рассмотрено", callback_data=f"resolve_complaint_{cid}")
        kb.button(text="❌ Отклонить", callback_data=f"reject_complaint_{cid}")
        await message.answer(text, reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("resolve_complaint_"))
async def resolve_complaint_handler(callback: CallbackQuery, **kwargs):
    cid = int(callback.data.split("_")[2])
    resolve_complaint(cid, 'reviewed')
    await callback.message.edit_text(callback.message.text + "\n\n✅ Жалоба обработана.")
    await callback.answer()

@router.callback_query(F.data.startswith("reject_complaint_"))
async def reject_complaint_handler(callback: CallbackQuery, **kwargs):
    cid = int(callback.data.split("_")[2])
    resolve_complaint(cid, 'rejected')
    await callback.message.edit_text(callback.message.text + "\n\n❌ Жалоба отклонена.")
    await callback.answer()

# ----------------- Логи -----------------
@router.message(Command("logs"))
@admin_group_only
async def show_logs(message: Message, **kwargs):
    args = message.text.split()
    limit = 50
    if len(args) > 1:
        try:
            limit = int(args[1])
        except:
            pass
    logs = get_logs(limit)
    if not logs:
        await message.answer("Логов нет.")
        return
    text = f"📋 Последние {limit} логов:\n\n"
    for log in logs:
        log_id, user_id, action, details, created = log
        text += f"{created} | {user_id} | {action} | {details or ''}\n"
    # Telegram имеет лимит 4096 символов, обрежем если нужно
    if len(text) > 4000:
        text = text[:4000] + "..."
    await message.answer(text)

# ----------------- Добавление админа -----------------
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