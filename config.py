import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "8613553204:AAFmNm9OZ2OCLj-VP8dJR4xbpDvErRczLK8")
ADMIN_GROUP_ID = int(os.getenv("ADMIN_GROUP_ID", "-5195330462"))

# Настройки ЮKassa
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "ваш_shop_id")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "ваш_секретный_ключ")
PROVIDER_TOKEN = os.getenv("PROVIDER_TOKEN", "ваш_токен_от_botfather")
CURRENCY = "RUB"
PAYMENT_AMOUNT = 1000  # можно изменить