from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def main_menu():
    kb = [
        [KeyboardButton(text="💰 Срочный выкуп")],
        [KeyboardButton(text="🔄 Я перекуп")],
        [KeyboardButton(text="🛍 Купить технику")],
        [KeyboardButton(text="❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def user_menu():
    kb = [
        [KeyboardButton(text="💰 Создать заявку на выкуп")],
        [KeyboardButton(text="📋 Мои заявки")],
        [KeyboardButton(text="🔔 Мои подписки")],
        [KeyboardButton(text="💸 Реферальная программа")],
        [KeyboardButton(text="💰 Мой кошелек")],
        [KeyboardButton(text="🛍 Купить технику")],
        [KeyboardButton(text="🔙 Главное меню")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def reseller_menu():
    kb = [
        [KeyboardButton(text="📦 Заявки на выкуп")],
        [KeyboardButton(text="🏷 Мои объявления")],
        [KeyboardButton(text="➕ Создать объявление")],
        [KeyboardButton(text="📝 Мои отзывы")],
        [KeyboardButton(text="🔔 Мои подписки")],
        [KeyboardButton(text="💸 Реферальная программа")],
        [KeyboardButton(text="💰 Мой кошелек")],
        [KeyboardButton(text="🛍 Купить технику")],
        [KeyboardButton(text="🔙 Главное меню")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def categories_inline_keyboard():
    from database import get_categories
    categories = get_categories()
    builder = InlineKeyboardBuilder()
    for cat_id, cat_name in categories:
        builder.button(text=cat_name, callback_data=f"cat_{cat_id}")
    builder.adjust(2)
    return builder.as_markup()

def brands_inline_keyboard(category_id):
    from database import get_brands_by_category
    brands = get_brands_by_category(category_id)
    if not brands:
        return None
    builder = InlineKeyboardBuilder()
    for brand_id, brand_name in brands:
        builder.button(text=brand_name, callback_data=f"brand_{brand_id}")
    builder.adjust(2)
    return builder.as_markup()

def models_inline_keyboard(brand_id):
    from database import get_models_by_brand
    models = get_models_by_brand(brand_id)
    if not models:
        return None
    builder = InlineKeyboardBuilder()
    for model_id, model_name in models:
        builder.button(text=model_name, callback_data=f"model_{model_id}")
    builder.adjust(2)
    return builder.as_markup()

def specs_multiselect_keyboard(model_id, selected_specs=None):
    from database import get_specs_by_model
    if selected_specs is None:
        selected_specs = []
    specs = get_specs_by_model(model_id)
    if not specs:
        return None
    builder = InlineKeyboardBuilder()
    for spec_id, spec_type, spec_value in specs:
        text = f"{spec_type}: {spec_value}"
        if spec_id in selected_specs:
            text = "✅ " + text
        builder.button(text=text, callback_data=f"spec_{spec_id}")
    builder.button(text="✅ Готово", callback_data="specs_done")
    builder.adjust(1)
    return builder.as_markup()

def buyout_request_inline_keyboard(request_id):
    kb = [
        [InlineKeyboardButton(text="💰 Предложить цену", callback_data=f"offer_{request_id}")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"refresh_req_{request_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def my_request_inline_keyboard(request_id):
    kb = [
        [InlineKeyboardButton(text="📊 Посмотреть предложения", callback_data=f"view_offers_{request_id}")],
        [InlineKeyboardButton(text="❌ Отменить заявку", callback_data=f"cancel_req_{request_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def offers_inline_keyboard(offers, request_id):
    builder = InlineKeyboardBuilder()
    for offer_id, reseller_id, price, created_at in offers:
        builder.button(text=f"{price} ₽ - выбрать", callback_data=f"choose_offer_{offer_id}_{request_id}")
    builder.adjust(1)
    return builder.as_markup()

def resale_lot_inline_keyboard(lot_id, price):
    kb = [
        [InlineKeyboardButton(text=f"🛒 Купить за {price} ₽", callback_data=f"buy_{lot_id}")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"refresh_lot_{lot_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def payment_keyboard():
    kb = [
        [InlineKeyboardButton(text="💳 500 ₽", callback_data="pay_500")],
        [InlineKeyboardButton(text="💳 1000 ₽", callback_data="pay_1000")],
        [InlineKeyboardButton(text="💳 2000 ₽", callback_data="pay_2000")],
        [InlineKeyboardButton(text="💳 5000 ₽", callback_data="pay_5000")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_wallet")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def subscriptions_multiselect_keyboard(current_subs):
    """Создаёт клавиатуру с чекбоксами для подписок на категории"""
    from database import get_categories
    categories = get_categories()
    builder = InlineKeyboardBuilder()
    for cat_id, cat_name in categories:
        # Если категория уже выбрана, ставим галочку
        prefix = "✅ " if cat_id in current_subs else "⬜ "
        builder.button(text=f"{prefix}{cat_name}", callback_data=f"sub_toggle_{cat_id}")
    # Кнопка для всех категорий
    all_text = "✅ Все категории" if None in current_subs else "⬜ Все категории"
    builder.button(text=all_text, callback_data="sub_toggle_all")
    builder.button(text="💾 Сохранить", callback_data="sub_save")
    builder.adjust(2)  # по 2 в ряд
    return builder.as_markup()