import asyncio
import logging
from aiogram import Bot, Dispatcher

from config import BOT_TOKEN
from database import init_db
from handlers import common, user, reseller, buyer, admin, payment, review

logging.basicConfig(level=logging.INFO)

async def main():
    init_db()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    
    dp.include_router(common.router)
    dp.include_router(user.router)
    dp.include_router(reseller.router)
    dp.include_router(buyer.router)
    dp.include_router(admin.router)
    dp.include_router(payment.router)
    dp.include_router(review.router)
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())