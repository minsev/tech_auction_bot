from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
import sqlite3

router = Router()

@router.message(Command("top"))
async def top_sellers(message: Message):
    conn = sqlite3.connect('tech_auction.db')
    cur = conn.cursor()
    # Топ по сумме продаж
    cur.execute('''
        SELECT reseller_id, SUM(price) as total, COUNT(*) as cnt
        FROM resale_lots
        WHERE status = 'sold'
        GROUP BY reseller_id
        ORDER BY total DESC
        LIMIT 10
    ''')
    top_by_sales = cur.fetchall()
    # Топ по рейтингу
    cur.execute('''
        SELECT seller_id, AVG(rating) as avg_rating, COUNT(*) as cnt
        FROM reviews
        GROUP BY seller_id
        HAVING cnt >= 3
        ORDER BY avg_rating DESC
        LIMIT 10
    ''')
    top_by_rating = cur.fetchall()
    conn.close()
    
    text = "🏆 **Топ продавцов**\n\n"
    text += "💰 **По объёму продаж:**\n"
    if top_by_sales:
        for i, (uid, total, cnt) in enumerate(top_by_sales, 1):
            contact = get_user_contact(uid)  # функция из database
            text += f"{i}. {contact} – {total} ₽ ({cnt} продаж)\n"
    else:
        text += "   пока нет данных\n"
    
    text += "\n⭐ **По рейтингу:**\n"
    if top_by_rating:
        for i, (uid, avg, cnt) in enumerate(top_by_rating, 1):
            contact = get_user_contact(uid)
            text += f"{i}. {contact} – {avg:.2f} ⭐ ({cnt} отзывов)\n"
    else:
        text += "   пока нет данных\n"
    
    await message.answer(text, parse_mode="Markdown")