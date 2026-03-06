from aiogram import Bot
from database import get_subscribers, get_resale_lot_by_id, get_user_contact

async def notify_new_lot(bot: Bot, lot_id: int):
    lot = get_resale_lot_by_id(lot_id)
    if not lot:
        return
    reseller_id = lot[1]
    category_id = lot[2]
    description = lot[6]
    price = lot[9]
    subscribers = get_subscribers(category_id)
    if not subscribers:
        return
    seller_contact = get_user_contact(reseller_id)
    message_text = (
        f"🆕 Новое объявление!\n"
        f"📝 {description}\n"
        f"💰 Цена: {price} ₽\n"
        f"👤 Продавец: {seller_contact}"
    )
    for uid in subscribers:
        try:
            await bot.send_message(uid, message_text)
        except Exception:
            pass